/**
 * Event tracker — singleton.
 *
 * Responsibilities (full design lives in
 * `apps/web/PHASE5_BACKEND_INTEGRATION_DISCOVERY.md` §Event tracker):
 *
 *   1. Persist every event to IndexedDB before scheduling a flush so that a
 *      reload/crash between enqueue and send doesn't lose data.
 *   2. Aggregate to send batches every ~3s **or** when 50 events accumulate,
 *      whichever fires first.
 *   3. Use `client_event_id` (UUIDv4) as the server-side idempotency key so
 *      retries on flaky networks never produce duplicate records.
 *   4. Fire on `visibilitychange`/`pagehide` with `keepalive: true` so events
 *      from a session about to be torn down still ship.
 *   5. Snapshot consent + customer identity at enqueue time so a later auth
 *      change doesn't accidentally upload events under the wrong identity.
 *
 * Multi-tab note: we deliberately do **not** elect a leader. The bulk
 * endpoint dedupes on `client_event_id` server-side, so worst case multiple
 * tabs send the same batch and one wins. That keeps this module simple and
 * tolerant of background tab throttling.
 */

import { ApiError, type IngestEventRequest } from "@/shared/api/contracts";
import { apiClient } from "@/shared/api/client";
import { useDebugEventStore } from "@/features/events/debug/store";
import { getSession } from "@/features/auth/tokenStore";
import {
  countPending,
  deleteEventsByIds,
  enqueueEvent,
  loadDueEvents,
  markRetry,
  purgeOtherIdentity,
  purgeStale,
  trimToMaxSize,
} from "@/features/events/tracker/storage";
import { shouldDropAsDuplicate } from "@/features/events/tracker/aggregation";
import { TRACKER_SCHEMA_VERSION, type StoredEvent, type TrackInput } from "@/features/events/tracker/types";

// --- tunables ---------------------------------------------------------------
const FLUSH_DEBOUNCE_MS = 3_000;
const FLUSH_SIZE_THRESHOLD = 50;
const MAX_BATCH_SIZE = 50;        // also matches server clamp
const MAX_QUEUE_SIZE = 1_000;
const MAX_EVENT_AGE_MS = 7 * 24 * 60 * 60 * 1_000;
const BACKOFF_BASE_MS = 1_000;
const BACKOFF_CAP_MS = 30_000;
const SESSION_STORAGE_KEY = "hyperpersona.tracker.session_id.v1";

// --- module state -----------------------------------------------------------
let consentSnapshot: string[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let flushInFlight: Promise<void> | null = null;
let consecutiveFailures = 0;

function genUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // Fallback for older Safari builds — RFC4122 v4 in pure JS.
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 16; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex
    .slice(8, 10)
    .join("")}-${hex.slice(10, 16).join("")}`;
}

function ensureSessionId(): string {
  if (typeof window === "undefined") return genUuid();
  try {
    const existing = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (existing) return existing;
    const fresh = genUuid();
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, fresh);
    return fresh;
  } catch {
    return genUuid();
  }
}

function isPersonalizationGranted(scopes: string[]): boolean {
  return scopes.includes("personalization");
}

function backoffDelay(attempts: number): number {
  // exponential, capped — `1s, 2s, 4s, …` then plateau at 30s.
  const exp = Math.min(BACKOFF_CAP_MS, BACKOFF_BASE_MS * 2 ** Math.max(0, attempts - 1));
  // Add a small jitter so multiple tabs don't synchronise their retries.
  const jitter = Math.floor(Math.random() * 250);
  return exp + jitter;
}

function clearFlushTimer(): void {
  if (flushTimer !== null) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
}

function scheduleFlush(delayMs = FLUSH_DEBOUNCE_MS): void {
  if (flushTimer !== null) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    void flushPending();
  }, delayMs);
}

// --- public API -------------------------------------------------------------

/**
 * Update the consent snapshot. Called from a React bridge that observes the
 * consent query. Events enqueued before this is set carry `[]` and the server
 * will reject them with `missing_personalization_scope` — at which point we
 * stop retrying them (see `flushPending` rejection handling).
 */
export function setConsentSnapshot(scopes: string[]): void {
  consentSnapshot = scopes.slice();
}

/** Read the current snapshot (mainly for tests/debug). */
export function getConsentSnapshot(): string[] {
  return consentSnapshot.slice();
}

/**
 * Enqueue a tracking event. Fire-and-forget — never throws to the caller.
 * Drops events when the user has not granted `personalization` consent
 * because the server would reject them anyway and we don't want to burn
 * IDB rows on doomed payloads.
 */
export function trackEvent(input: TrackInput): void {
  if (typeof window === "undefined") return;

  // Only do the dedupe check after we know we're going to enqueue — the
  // dedupe cache is a best-effort guard, not a hard contract.
  if (shouldDropAsDuplicate(input.event_type, input.payload)) return;

  const scopes = (input.consent_scope?.length ? input.consent_scope : consentSnapshot).slice();
  if (!isPersonalizationGranted(scopes)) {
    // Without personalization scope the server rejects everything in the
    // batch (see `server/src/routes/events.py`). Drop early.
    return;
  }

  const session = getSession();
  if (!session) {
    // Anonymous browsing — there is no JWT to send under, so there's no point
    // queuing. The user must sign in for tracking to attach to their record.
    return;
  }

  const stored: StoredEvent = {
    client_event_id: genUuid(),
    event_type: input.event_type,
    payload: input.payload,
    consent_scope: scopes,
    client_emitted_at: Date.now(),
    client_session_id: ensureSessionId(),
    schema_version: TRACKER_SCHEMA_VERSION,
    attempt_count: 0,
    next_attempt_at: 0,
    customer_id_at_enqueue: session.customerId,
  };

  // Show in the dev trace immediately so the panel reflects user intent
  // even before we've heard back from the server.
  try {
    useDebugEventStore.getState().push({
      event_id: stored.client_event_id,
      event_type: stored.event_type,
      payload: stored.payload,
      status: "queued",
      created_at: new Date(stored.client_emitted_at).toISOString(),
    });
  } catch {
    /* noop — debug surface is non-critical. */
  }

  void (async () => {
    try {
      await enqueueEvent(stored);
      // Trim once after enqueue so a runaway producer can't grow forever.
      await trimToMaxSize(MAX_QUEUE_SIZE);
      const pending = await countPending();
      if (pending >= FLUSH_SIZE_THRESHOLD) {
        clearFlushTimer();
        void flushPending();
      } else {
        scheduleFlush();
      }
    } catch (err) {
      // IDB unavailable — still surface to the debug log, but otherwise we
      // can't persist. This is a hard environment limitation; nothing
      // graceful to do beyond fall through to the next event.
      if (import.meta.env?.DEV) console.warn("[tracker] enqueue failed", err);
    }
  })();
}

/**
 * Flush pending events. Idempotent: concurrent callers all share the same
 * in-flight promise so we never start two flushes at once.
 */
export function flushPending(opts: { keepalive?: boolean } = {}): Promise<void> {
  if (flushInFlight) return flushInFlight;
  flushInFlight = (async () => {
    try {
      await drainOnce(opts.keepalive ?? false);
    } finally {
      flushInFlight = null;
    }
    // If anything remains and we're online + auth'd, schedule another pass.
    if (typeof navigator !== "undefined" && !navigator.onLine) return;
    if (!getSession()) return;
    const pending = await countPending().catch(() => 0);
    if (pending > 0) {
      scheduleFlush(consecutiveFailures > 0 ? backoffDelay(consecutiveFailures) : FLUSH_DEBOUNCE_MS);
    }
  })();
  return flushInFlight;
}

async function drainOnce(keepalive: boolean): Promise<void> {
  const session = getSession();
  if (!session) return; // No auth → no flush. Events stay in IDB.

  const due = await loadDueEvents(MAX_BATCH_SIZE).catch(() => [] as StoredEvent[]);
  if (due.length === 0) return;

  // Identity guard: don't ship events queued under a different `customer_id`
  // — that would be a privacy leak. Purge them and try again on the next tick.
  const wrongIdentity = due.filter((e) => e.customer_id_at_enqueue && e.customer_id_at_enqueue !== session.customerId);
  if (wrongIdentity.length > 0) {
    await deleteEventsByIds(wrongIdentity.map((e) => e.client_event_id));
  }
  const safe = due.filter((e) => !wrongIdentity.includes(e));
  if (safe.length === 0) return;

  const wire: IngestEventRequest[] = safe.map((e) => ({
    client_event_id: e.client_event_id,
    event_type: e.event_type,
    payload: e.payload,
    consent_scope: e.consent_scope,
  }));

  let response: Awaited<ReturnType<typeof apiClient.trackEventsBatch>>;
  try {
    response = await apiClient.trackEventsBatch(wire, { keepalive });
  } catch (err) {
    // Network or 5xx — keep events queued and back off. 401 already cleared
    // the session in `request()`; we'll resume on next login.
    consecutiveFailures += 1;
    const status = err instanceof ApiError ? err.status : 0;
    const isRetryable = !(err instanceof ApiError) || err.retryable;
    if (!isRetryable) {
      // 4xx (other than 401) means the request itself is malformed — drop the
      // batch so we don't retry-storm into the wall.
      await deleteEventsByIds(safe.map((e) => e.client_event_id));
      consecutiveFailures = 0;
      if (import.meta.env?.DEV) console.warn(`[tracker] dropping batch on non-retryable ${status}`, err);
      return;
    }
    const nextAttempt = Date.now() + backoffDelay(consecutiveFailures);
    await markRetry(
      safe.map((e) => e.client_event_id),
      nextAttempt,
    );
    return;
  }

  consecutiveFailures = 0;

  // Ack: events with status="queued" are durable on the server; rejected
  // events are also terminal (server told us why) and shouldn't be retried.
  const terminalIds = response.results
    .filter((r) => r.status === "queued" || r.status === "rejected")
    .map((r) => r.client_event_id);
  await deleteEventsByIds(terminalIds);

  // Surface server outcomes to the debug panel so devs see rejections too.
  try {
    const store = useDebugEventStore.getState();
    for (const r of response.results) {
      const original = safe.find((s) => s.client_event_id === r.client_event_id);
      if (!original) continue;
      store.push({
        event_id: r.event_id ?? r.client_event_id,
        event_type: original.event_type,
        payload: original.payload,
        status: r.status === "queued" ? "sent" : "rejected",
        created_at: new Date().toISOString(),
        reason: r.reason,
      });
    }
  } catch {
    /* noop */
  }
}

/**
 * Purge everything in the queue. Called from auth identity-change handlers
 * and from the right-to-erase flow when the user wipes their account.
 */
export async function clearTrackerQueue(): Promise<void> {
  await purgeOtherIdentity(null);
  consecutiveFailures = 0;
}

/**
 * Boot-time housekeeping. Called once from `init.ts` and again whenever
 * identity changes. Drops stale rows, realigns the queue to the current
 * identity, and schedules an immediate drain if anything remains.
 */
export async function trackerBootDrain(): Promise<void> {
  await purgeStale(Date.now() - MAX_EVENT_AGE_MS).catch(() => 0);
  const session = getSession();
  if (session) {
    // Purge events queued under any *other* identity. Events queued
    // anonymously (customerId === null) never make it into IDB today
    // — `trackEvent` rejects unauthenticated calls — so this is safe.
    await purgeOtherIdentity(session.customerId).catch(() => 0);
    const pending = await countPending().catch(() => 0);
    if (pending > 0) scheduleFlush(50);
  }
}

/** Public hook for tests. */
export const _tracker = {
  scheduleFlush,
  clearFlushTimer,
  FLUSH_DEBOUNCE_MS,
  FLUSH_SIZE_THRESHOLD,
  MAX_BATCH_SIZE,
};

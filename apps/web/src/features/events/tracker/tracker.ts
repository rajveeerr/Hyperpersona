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
/** Server clamps `IngestBatchRequest.events` at 100; mirror that ceiling here. */
const MAX_BATCH_SIZE = 100;
/**
 * `keepalive: true` browser bodies are capped at ~64 KB **per origin** —
 * any other in-flight keepalive request shares the same budget. Stay well
 * under the cap so a concurrent fetch (e.g. the cart mutation that's also
 * trying to fire on pagehide) doesn't get squeezed out. Non-keepalive
 * flushes (debounce/threshold) are not subject to this cap.
 */
const KEEPALIVE_BYTE_CAP = 50_000;
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

function intersectScopes(requested: string[], granted: string[]): string[] {
  if (requested.length === 0) return [];
  const grantedSet = new Set(granted);
  return requested.filter((s) => grantedSet.has(s));
}

/**
 * Estimate the encoded byte cost of a single event on the wire. We only
 * need the wire-relevant fields — IDB-internal bookkeeping (attempt_count,
 * customer_id_at_enqueue, etc.) is dropped before send. `Blob.size` is the
 * one cross-browser way to count UTF-8 bytes accurately.
 */
function eventWireBytes(e: StoredEvent): number {
  const wire = {
    client_event_id: e.client_event_id,
    event_type: e.event_type,
    payload: e.payload,
    consent_scope: e.consent_scope,
  };
  return new Blob([JSON.stringify(wire)]).size;
}

/**
 * Trim an event list down so the encoded payload fits inside `cap` bytes,
 * leaving overhead headroom for the `{events:[...]}` envelope and HTTP
 * headers. Preserves prefix order so older events ship first; remaining
 * events stay in the queue and ride the next flush.
 */
function trimToByteCap(events: StoredEvent[], cap: number): StoredEvent[] {
  // Reserve ~1 KB for the JSON envelope (`{"events":[...]}`) plus headers.
  const budget = Math.max(1_024, cap - 1_024);
  const out: StoredEvent[] = [];
  let used = 0;
  for (const e of events) {
    const cost = eventWireBytes(e) + 1; // +1 for the comma separator
    if (used + cost > budget && out.length > 0) break;
    out.push(e);
    used += cost;
  }
  return out;
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
 * consent query. Used by `trackEvent` to gate enqueue: an event is dropped
 * locally only if the intersection of its declared `consent_scope` and this
 * snapshot is empty. Events that survive the intersection ship the
 * intersected scope list on the wire so the server stores the right thing.
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
 * Drops events whose declared scopes share nothing with the customer's
 * granted scopes, because the server would reject them anyway and we don't
 * want to burn IDB rows on doomed payloads. Surviving events ship the
 * intersected scope list on the wire so the server records what the event
 * is actually allowed to be used for (matches the per-event scope check
 * in `server/src/routes/events.py`).
 */
export function trackEvent(input: TrackInput): void {
  if (typeof window === "undefined") return;

  // Only do the dedupe check after we know we're going to enqueue — the
  // dedupe cache is a best-effort guard, not a hard contract.
  if (shouldDropAsDuplicate(input.event_type, input.payload)) return;

  // Default to {"analytics"} when the caller doesn't declare a scope, since
  // every event is at minimum a recordable analytics signal.
  const requested = input.consent_scope?.length ? input.consent_scope : ["analytics"];
  const scopes = intersectScopes(requested, consentSnapshot);
  if (scopes.length === 0) {
    // Snapshot grants none of the scopes this event needs. Either the user
    // has no consent record yet, or they've revoked the relevant scope —
    // drop instead of queuing a payload the server will reject.
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
  const safeAll = due.filter((e) => !wrongIdentity.includes(e));
  if (safeAll.length === 0) return;

  // Trim by bytes when the page is being torn down (keepalive=true). The
  // browser caps keepalive bodies at ~64 KB across all in-flight requests
  // for the origin; oversize requests fail silently. For non-keepalive
  // flushes we trust the server's 100-event clamp and skip the byte check.
  const safe = keepalive ? trimToByteCap(safeAll, KEEPALIVE_BYTE_CAP) : safeAll;
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

/**
 * Type vocabulary for the FE event tracker. Wire types match
 * `apps/web/PHASE5_BACKEND_INTEGRATION_DISCOVERY.md` and the canonical
 * server-side shapes in `shared/schemas.py`.
 *
 * Keep these in sync when either side changes. The discovery doc is the
 * source of truth for batching/reliability semantics.
 */

import type { IngestEventRequest } from "@/shared/api/contracts";

/** Bumped if `StoredEvent` shape changes incompatibly — old rows are dropped at boot. */
export const TRACKER_SCHEMA_VERSION = 1;

/**
 * Persisted event in IndexedDB. Adds local metadata the server doesn't see.
 * `customer_id_at_enqueue` is local-only — it lets us purge events queued
 * under a previous identity if the user signs in as somebody else, since
 * each event will be sent under whatever JWT is current at flush time.
 */
export type StoredEvent = IngestEventRequest & {
  client_emitted_at: number;          // epoch ms — Date.now() at enqueue
  client_session_id: string;
  schema_version: number;
  attempt_count: number;
  next_attempt_at: number;            // epoch ms — backoff scheduler reads this
  customer_id_at_enqueue: string | null;
};

/** Public input for `trackEvent()` — fire-and-forget. */
export type TrackInput = {
  event_type: string;
  payload: Record<string, unknown>;
  /** Optional override; tracker snapshots current consent if omitted. */
  consent_scope?: string[];
};

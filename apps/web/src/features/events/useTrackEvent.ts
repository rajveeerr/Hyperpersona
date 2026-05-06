import { useCallback } from "react";

import { trackEvent as enqueueTrackedEvent } from "@/features/events/tracker";

/**
 * Legacy call-site shape preserved for backwards compatibility — every existing
 * callsite passes `customer_id`, but the real backend ignores it (identity
 * comes from the JWT). The field is dropped on the way to the tracker; do not
 * rely on it for anything.
 */
type LegacyTrackInput = {
  customer_id?: string;
  event_type: string;
  payload: Record<string, unknown>;
  consent_scope?: string[];
};

/**
 * Hook returns a stable `track(input)` callback. Internally this just enqueues
 * to the singleton event tracker; the tracker handles batching, IDB persistence,
 * idempotency, retries, and unload-time keepalive flushes — see
 * `apps/web/src/features/events/tracker/tracker.ts` for the full design.
 */
export function useTrackEvent() {
  return useCallback((input: LegacyTrackInput) => {
    // `customer_id` is intentionally ignored — server resolves identity from JWT.
    enqueueTrackedEvent({
      event_type: input.event_type,
      payload: input.payload,
      consent_scope: input.consent_scope,
    });
  }, []);
}

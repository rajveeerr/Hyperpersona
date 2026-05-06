import { useCallback } from "react";

import { trackEvent as enqueueTrackedEvent } from "@/features/events/tracker";

type TrackInput = {
  event_type: string;
  payload: Record<string, unknown>;
  consent_scope?: string[];
};

/**
 * Hook returns a stable `track(input)` callback. Internally this just enqueues
 * to the singleton event tracker; the tracker handles batching, IDB persistence,
 * idempotency, retries, and unload-time keepalive flushes — see
 * `apps/web/src/features/events/tracker/tracker.ts` for the full design.
 *
 * Identity comes from the JWT server-side — there is no `customer_id` field
 * on the wire. For events with a fixed payload shape from the spec, prefer
 * `useSpecTrack` so the compiler enforces it.
 */
export function useTrackEvent() {
  return useCallback((input: TrackInput) => {
    enqueueTrackedEvent(input);
  }, []);
}

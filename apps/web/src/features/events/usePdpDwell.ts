/**
 * Single-shot PDP dwell tracker.
 *
 * Spec rule (`event-types-description.md` §1):
 *   - Fire `product_dwell` when the user stays ≥10s on the PDP.
 *   - At most once per page load.
 *   - Don't accumulate time while the tab is hidden — a tab buried in the
 *     background for an hour shouldn't count as a 3,600s dwell.
 *
 * Implementation:
 *   - Track an `accumulatedMs` counter that only advances while the document
 *     is visible.
 *   - On unmount/route-change/identity-change, fire once if accumulated ≥10s
 *     and not already fired (we also fire eagerly the moment we cross 10s
 *     while still on the page so it ships before navigation).
 */

import { useEffect, useRef } from "react";

import { useSpecTrack } from "@/features/events/specEvents";

const DWELL_THRESHOLD_MS = 10_000;

type PdpDwellInput = {
  /** Stable product identifier — must change to reset the timer. */
  product_id: string;
  category: string;
};

export function usePdpDwell({ product_id, category }: PdpDwellInput): void {
  const track = useSpecTrack();
  const trackRef = useRef(track);
  trackRef.current = track;

  useEffect(() => {
    if (typeof document === "undefined") return;
    if (!product_id) return;

    let accumulatedMs = 0;
    let lastVisibleAt = document.visibilityState === "visible" ? Date.now() : null;
    let fired = false;
    let crossTimer: ReturnType<typeof setTimeout> | null = null;

    const fire = () => {
      if (fired) return;
      fired = true;
      if (crossTimer !== null) {
        clearTimeout(crossTimer);
        crossTimer = null;
      }
      const seconds = Math.max(
        DWELL_THRESHOLD_MS,
        accumulatedMs + (lastVisibleAt !== null ? Date.now() - lastVisibleAt : 0),
      ) / 1_000;
      trackRef.current("product_dwell", {
        product_id,
        category,
        duration_seconds: Math.round(seconds),
      });
    };

    const scheduleCrossover = () => {
      if (fired || crossTimer !== null) return;
      const remaining = DWELL_THRESHOLD_MS - accumulatedMs;
      if (remaining <= 0) {
        fire();
        return;
      }
      crossTimer = setTimeout(fire, remaining);
    };

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        if (lastVisibleAt === null) lastVisibleAt = Date.now();
        scheduleCrossover();
      } else {
        // Pause: bank the visible time, cancel the pending crossover so it
        // doesn't fire while the user is on a different tab.
        if (lastVisibleAt !== null) {
          accumulatedMs += Date.now() - lastVisibleAt;
          lastVisibleAt = null;
        }
        if (crossTimer !== null) {
          clearTimeout(crossTimer);
          crossTimer = null;
        }
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    if (document.visibilityState === "visible") scheduleCrossover();

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      if (crossTimer !== null) {
        clearTimeout(crossTimer);
        crossTimer = null;
      }
      // Final accounting on unmount — fire if we crossed the threshold but
      // hadn't yet emitted (e.g. user crossed 10s and then navigated away
      // before the timer's tick ran).
      const total = accumulatedMs + (lastVisibleAt !== null ? Date.now() - lastVisibleAt : 0);
      if (!fired && total >= DWELL_THRESHOLD_MS) fire();
    };
  }, [product_id, category]);
}

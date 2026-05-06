/**
 * Typed builders for the events listed in `apps/web/event-types-description.md`.
 *
 * Each spec event has a strict payload shape — using `useSpecTrack` instead of
 * raw `useTrackEvent` turns missing/wrong fields into TypeScript errors at the
 * callsite, so analytics drift can't silently slip into the codebase.
 *
 * Free-form events that aren't in the spec (e.g. PDP variant changes,
 * `recommendation_impression`) keep using `useTrackEvent` directly.
 */

import { useCallback } from "react";

import { useTrackEvent } from "@/features/events/useTrackEvent";

export type SpecEvents = {
  search: { query: string; results_count: number };
  product_view: {
    product_id: string;
    product_name: string;
    category: string;
    price: number;
  };
  product_dwell: {
    product_id: string;
    category: string;
    duration_seconds: number;
  };
  category_view: { category: string };
  filter_applied: {
    category: string;
    filter_type: string;
    filter_value: string;
  };
  add_to_cart: {
    product_id: string;
    product_name: string;
    category: string;
    price: number;
    quantity: number;
  };
  remove_from_cart: { product_id: string; category: string };
  wishlist_add: {
    product_id: string;
    product_name: string;
    category: string;
  };
  wishlist_remove: { product_id: string; category: string };
  purchase: {
    product_id: string;
    product_name: string;
    category: string;
    price: number;
    quantity: number;
  };
  review_submitted: { product_id: string; rating: number; summary: string };
  recommendation_clicked: {
    product_id: string;
    category: string;
    source_context: string;
  };
};

export type SpecEventType = keyof SpecEvents;

/**
 * Returns a stable `track(event_type, payload)` callback that enforces spec
 * payload shapes. Stamps `consent_scope` with the canonical
 * `["analytics", "personalization"]` so callsites don't drift on that either.
 */
export function useSpecTrack() {
  const track = useTrackEvent();
  return useCallback(
    <K extends SpecEventType>(event_type: K, payload: SpecEvents[K]) => {
      track({
        event_type,
        payload: payload as Record<string, unknown>,
        consent_scope: ["analytics", "personalization"],
      });
    },
    [track],
  );
}

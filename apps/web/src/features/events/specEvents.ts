/**
 * Typed builders for the events listed in `apps/web/event-types-description.md`.
 *
 * Each spec event has a strict payload shape — using `useSpecTrack` instead of
 * raw `useTrackEvent` turns missing/wrong fields into TypeScript errors at the
 * callsite, so analytics drift can't silently slip into the codebase.
 *
 * Free-form events that aren't in the spec (e.g. PDP variant changes,
 * `recommendation_impression`) keep using `useTrackEvent` directly.
 *
 * Commerce events embed `ProductSnapshot` so the worker sees the same
 * brand/rating/vertical/freeDelivery context regardless of where the event
 * originated. Build payloads through helpers in `payloads.ts` rather than
 * hand-typing fields at every callsite — that's how the snapshot stays in
 * sync with the in-memory cache that fills cart/wishlist gaps.
 */

import { useCallback } from "react";

import type { ProductSnapshot, VariantSnapshot } from "@/features/events/payloads";
import { useTrackEvent } from "@/features/events/useTrackEvent";

/**
 * Per-event payload shapes. Required fields are spec-mandated; everything
 * coming via `ProductSnapshot` is required at minimum (id/name/category/price)
 * with optional context auto-included by the helper. Callsites are still
 * free to add extra keys via the `& Record<string, unknown>` extension on
 * `useSpecTrack` — handy for one-off context like rail source / rec rank.
 */
export type SpecEvents = {
  search: {
    query: string;
    results_count: number;
    /** Page index (1-based) when paged. */
    page?: number;
    /** Sort key currently applied (relevance / price-asc / etc.). */
    sort?: string;
  };
  product_view: ProductSnapshot;
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
    /** Optional surface — "catalog" / "search" / "wishlist" — so the worker
     *  can tell which page the filter was applied on. */
    surface?: string;
  };
  add_to_cart: ProductSnapshot & {
    quantity: number;
    /** PDP variant context (color/size/storage) when available. */
    variant?: VariantSnapshot;
    /** "pdp" | "rail" | "complement" — where the add was initiated. */
    source?: string;
  };
  remove_from_cart: ProductSnapshot & {
    /** Quantity that was on the line at the moment of removal. */
    quantity_removed: number;
    /** Cart line subtotal at removal time (unit_price × quantity). */
    line_total: number;
    variant?: VariantSnapshot;
  };
  cart_quantity_changed: ProductSnapshot & {
    quantity_old: number;
    quantity_new: number;
    /** Signed delta — +1 / -1 / +2 etc. */
    delta: number;
    variant?: VariantSnapshot;
  };
  wishlist_add: ProductSnapshot & {
    variant?: VariantSnapshot;
    source?: string;
  };
  wishlist_remove: ProductSnapshot;
  purchase: ProductSnapshot & {
    quantity: number;
    line_total: number;
    /** Set so the worker can group per-line events back into one order. */
    order_id: string;
    variant?: VariantSnapshot;
  };
  /** Order-level summary — fires once per checkout, alongside per-line `purchase` events. */
  order_placed: {
    order_id: string;
    subtotal: number;
    /** Number of distinct SKUs in the order. */
    line_count: number;
    /** Total units across all lines. */
    item_count: number;
    payment_method: string;
    country: string;
    city?: string;
    /** Categories represented in the basket — useful for cross-category propensity. */
    categories?: string[];
  };
  review_submitted: { product_id: string; rating: number; summary: string };
  recommendation_clicked: {
    product_id: string;
    category: string;
    source_context: string;
    /** Position in the rail (1-based). */
    rank?: number;
    /** True when the rail was personalized (had a `personalization_reason`). */
    personalized?: boolean;
  };
};

export type SpecEventType = keyof SpecEvents;

/**
 * Returns a stable `track(event_type, payload)` callback that enforces spec
 * payload shapes while still allowing callsites to add ad-hoc context as
 * extra keys (`& Record<string, unknown>`). Stamps `consent_scope` with the
 * canonical `["analytics", "personalization"]` so callsites don't drift.
 */
export function useSpecTrack() {
  const track = useTrackEvent();
  return useCallback(
    <K extends SpecEventType>(
      event_type: K,
      payload: SpecEvents[K] & Record<string, unknown>,
    ) => {
      track({
        event_type,
        payload: payload as Record<string, unknown>,
        consent_scope: ["analytics", "personalization"],
      });
    },
    [track],
  );
}

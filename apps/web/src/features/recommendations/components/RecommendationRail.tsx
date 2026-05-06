import { useEffect, useRef } from "react";

import { ProductGrid } from "@/features/catalog/components/ProductGrid";
import { useSpecTrack } from "@/features/events/specEvents";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import type { Product } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

type RecommendationRailProps = {
  /**
   * Products to render. Callers convert from the BE's `RecommendProduct[]`
   * (or `Product[]` for non-`/recommend` surfaces like `/catalog/popular`)
   * into the canonical `Product` shape that `ProductGrid` consumes.
   */
  products: Product[];
  /**
   * The `/recommend?context=...` value this rail was rendered for. Stamped
   * into `recommendation_clicked.source_context` so backend analytics can
   * attribute clicks to the surface that produced them. Build with
   * `Context.*` helpers, never hand-roll the string.
   */
  sourceContext: string;
  /** Static rail heading chosen at the call site. */
  title: string;
  /** Optional eyebrow above the title (e.g. "Recommended for you"). */
  subtitle?: string;
  /**
   * Prose under the title. Pass `personalization_reason` from the
   * `/recommend` response when personalized; a static string when generic.
   */
  reason?: string;
  /**
   * Whether the BE ran a personalized path. Renders a "Generic mode" pill
   * when false. Derived at the call site from `personalization_reason !== null`
   * for `/recommend`, or hardcoded `false` for popular-products fallbacks.
   */
  personalized?: boolean;
  /**
   * `editorial` — home personalized strip (cream/white story).
   * `pdp` — product page; same micro-label + prose with quieter chrome.
   */
  presentation?: "default" | "editorial" | "pdp";
};

const pdpRailTitle =
  "font-display font-normal tracking-display text-balance text-ink antialiased leading-[1.06] text-[clamp(1.45rem,2.6vw,2.1rem)]";

export function RecommendationRail({
  products,
  sourceContext,
  title,
  subtitle,
  reason,
  personalized = true,
  presentation = "default",
}: RecommendationRailProps) {
  const track = useTrackEvent();
  const trackSpec = useSpecTrack();
  const isEditorial = presentation === "editorial";
  const isPdp = presentation === "pdp";
  const isLanding = isEditorial || isPdp;
  const cardAccent = isPdp ? (personalized ? "Curated pairing" : "Catalog fallback") : "Why this surfaced";

  const impressionTrackedRef = useRef(false);
  useEffect(() => {
    if (impressionTrackedRef.current) return;
    if (products.length === 0) return;
    impressionTrackedRef.current = true;
    track({
      event_type: "recommendation_impression",
      payload: {
        title,
        personalized,
        surface: presentation,
        source_context: sourceContext,
        product_count: products.length,
        // Ship the ranked id list so the worker can compute impression-to-click
        // curves per (rail, position). Capped at 24 to keep the payload
        // bounded — rails with more rows are rare and the tail rarely converts.
        product_ids: products.slice(0, 24).map((p) => p.id),
        categories: Array.from(new Set(products.map((p) => p.category))).filter(Boolean),
      },
      consent_scope: ["analytics", "personalization"],
    });
  }, [track, title, personalized, presentation, sourceContext, products.length]);

  if (products.length === 0) return null;

  return (
    <section className={`flex flex-col ${isLanding ? "gap-7 sm:gap-8" : "gap-5"}`}>
      <div className={`${tw.flexBetween} flex-col gap-4 sm:flex-row sm:items-start`}>
        <div className={tw.stackSm}>
          {subtitle ? (
            isLanding ? (
              <p className={`text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>{subtitle}</p>
            ) : (
              <span className={tw.eyebrow}>{subtitle}</span>
            )
          ) : null}
          <h2
            className={
              isPdp
                ? pdpRailTitle
                : `${tw.displayH2} ${isEditorial ? "text-[clamp(1.5rem,2.8vw,2.25rem)] leading-[1.06]" : "text-2xl"}`
            }
          >
            {title}
          </h2>
          {reason ? (
            <p
              className={
                isLanding
                  ? `max-w-3xl text-pretty text-sm leading-relaxed text-ink/88 sm:text-[0.9375rem] sm:leading-relaxed`
                  : tw.muted
              }
            >
              {reason}
            </p>
          ) : null}
        </div>
        {!personalized ? (
          <span className={`${tw.chip} shrink-0`}>Generic mode</span>
        ) : null}
      </div>
      <ProductGrid
        products={products}
        accent={cardAccent}
        onProductClick={(product) => {
          // Rail is pre-ranked, so position in `products` is the displayed rank.
          const idx = products.findIndex((p) => p.id === product.id);
          trackSpec("recommendation_clicked", {
            product_id: product.id,
            category: product.category,
            source_context: sourceContext,
            personalized,
            ...(idx >= 0 ? { rank: idx + 1 } : {}),
          });
        }}
      />
    </section>
  );
}

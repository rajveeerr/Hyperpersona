import { useEffect, useRef, useState } from "react";

import { formatConfidence } from "@/shared/lib/format";
import type { RecommendationRail as RecommendationRailType } from "@/shared/api/contracts";
import { useSpecTrack } from "@/features/events/specEvents";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import { tw } from "@/shared/ui/tw";

import { ProductGrid } from "@/features/catalog/components/ProductGrid";
import { RecommendationAuditDrawer } from "@/features/recommendations/components/RecommendationAuditDrawer";

type RecommendationRailProps = {
  rail: RecommendationRailType;
  /**
   * The `/recommend?context=...` value this rail was rendered for. Required —
   * we stamp it into `recommendation_clicked.source_context` so the backend
   * can attribute clicks to the surface that produced them. Build with
   * `Context.*` helpers, never hand-roll the string.
   */
  sourceContext: string;
  /**
   * `editorial` — home personalized strip (cream/white story).
   * `pdp` — product page: same micro-label + prose as editorial, quieter confidence pill, pairing accent on cards.
   */
  presentation?: "default" | "editorial" | "pdp";
};

const pdpRailTitle =
  "font-display font-normal tracking-display text-balance text-ink antialiased leading-[1.06] text-[clamp(1.45rem,2.6vw,2.1rem)]";

const confidencePillPdp =
  "shrink-0 rounded-pill border border-outline/45 bg-white/55 px-3 py-2 text-center text-[0.65rem] font-semibold uppercase tracking-ui-wide text-ink/85 shadow-[0_6px_20px_rgba(34,28,23,0.05)] backdrop-blur-[6px]";

export function RecommendationRail({ rail, sourceContext, presentation = "default" }: RecommendationRailProps) {
  const track = useTrackEvent();
  const trackSpec = useSpecTrack();
  const [auditOpen, setAuditOpen] = useState(false);
  const impressionTrackedRef = useRef(false);
  const isEditorial = presentation === "editorial";
  const isPdp = presentation === "pdp";
  const isLanding = isEditorial || isPdp;

  const cardAccent = isPdp ? (rail.fallback ? "Catalog fallback" : "Curated pairing") : "Why this surfaced";

  useEffect(() => {
    if (impressionTrackedRef.current) return;
    impressionTrackedRef.current = true;
    track({
      event_type: "recommendation_impression",
      payload: {
        railId: rail.id,
        title: rail.title,
        fallback: rail.fallback,
        confidence: rail.confidence,
        surface: presentation,
        source_context: sourceContext,
      },
      consent_scope: ["analytics", "personalization"],
    });
  }, [track, rail.id, rail.title, rail.fallback, rail.confidence, presentation, sourceContext]);

  return (
    <>
      <section className={`flex flex-col ${isLanding ? "gap-7 sm:gap-8" : "gap-5"}`}>
      <div className={`${tw.flexBetween} flex-col gap-4 sm:flex-row sm:items-start`}>
        <div className={tw.stackSm}>
          {isLanding ? (
            <p className={`text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>{rail.subtitle}</p>
          ) : (
            <span className={tw.eyebrow}>{rail.subtitle}</span>
          )}
          <h2
            className={
              isPdp
                ? pdpRailTitle
                : `${tw.displayH2} ${isEditorial ? "text-[clamp(1.5rem,2.8vw,2.25rem)] leading-[1.06]" : "text-2xl"}`
            }
          >
            {rail.title}
          </h2>
          <p
            className={
              isLanding
                ? `max-w-3xl text-pretty text-sm leading-relaxed text-ink/88 sm:text-[0.9375rem] sm:leading-relaxed`
                : tw.muted
            }
          >
            {rail.reason}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={isPdp ? confidencePillPdp : `${tw.chip} shrink-0`}>
            {rail.fallback ? "Generic mode" : formatConfidence(rail.confidence)}
          </span>
          <button
            type="button"
            className={tw.buttonGhost}
            onClick={() => {
              setAuditOpen(true);
              track({
                event_type: "recommendation_audit_opened",
                payload: { railId: rail.id, surface: presentation, source_context: sourceContext },
                consent_scope: ["analytics", "personalization"],
              });
            }}
          >
            Audit
          </button>
        </div>
      </div>
      <ProductGrid
        products={rail.products}
        accent={cardAccent}
        onProductClick={(product) =>
          trackSpec("recommendation_clicked", {
            product_id: product.id,
            category: product.category,
            source_context: sourceContext,
          })
        }
      />
      </section>
      <RecommendationAuditDrawer rail={rail} open={auditOpen} onClose={() => setAuditOpen(false)} />
    </>
  );
}


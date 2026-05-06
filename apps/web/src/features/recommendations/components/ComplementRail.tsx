/**
 * "Frequently bought together" rail for the Cart surface.
 *
 * Backed by `GET /recommend/complement?cart_items=...`. The BE response
 * intentionally ships a lighter shape than `/recommend` (no image, no brand,
 * no rating, no reviewCount) so we render a text-forward "list" tile rather
 * than the catalog product grid. Each row links to the PDP and offers a
 * one-click add-to-cart.
 *
 * Tracked events:
 *   - `recommendation_impression` once on first render with `source_context`
 *   - `recommendation_clicked` per product link click (uses `cart_complement`
 *     as the source_context — distinct namespace from the spec `Context.*`
 *     values so analytics can isolate complement vs `cart_active` rails).
 */

import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

import { prefetchProductPageChunk } from "@/app/routeChunks";
import { useAddToCart } from "@/features/cart/useCart";
import { fromComplementProduct, rememberProducts } from "@/features/events/payloads";
import { useSpecTrack } from "@/features/events/specEvents";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import { pushToast } from "@/features/toast/store";
import type { ComplementProduct } from "@/shared/api/contracts";
import { formatCurrency } from "@/shared/lib/format";
import { tw } from "@/shared/ui/tw";

const COMPLEMENT_SOURCE_CONTEXT = "cart_complement";

type ComplementRailProps = {
  recommendations: ComplementProduct[];
};

export function ComplementRail({ recommendations }: ComplementRailProps) {
  const track = useTrackEvent();
  const trackSpec = useSpecTrack();
  const addToCart = useAddToCart();
  const impressionTrackedRef = useRef(false);

  useEffect(() => {
    // Stamp categories first so a click that fires before the impression
    // effect re-runs still has a category to stamp on `recommendation_clicked`.
    rememberProducts(recommendations);
    if (impressionTrackedRef.current) return;
    if (recommendations.length === 0) return;
    impressionTrackedRef.current = true;
    track({
      event_type: "recommendation_impression",
      payload: {
        title: "Frequently bought together",
        surface: "cart_complement",
        source_context: COMPLEMENT_SOURCE_CONTEXT,
        product_count: recommendations.length,
      },
      consent_scope: ["analytics", "personalization"],
    });
  }, [track, recommendations]);

  if (recommendations.length === 0) return null;

  return (
    <section className="flex flex-col gap-5">
      <header className="max-w-3xl">
        <p className={`text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>
          Bundle finishers
        </p>
        <h2 className={`${tw.displayH2} mt-1 text-2xl`}>Frequently bought together</h2>
        <p className={`mt-2 text-sm leading-relaxed ${tw.muted}`}>
          Picks the recommender pairs with what's already in your bag. Light add-on
          shapes — no image, just the why and a one-tap add.
        </p>
      </header>

      <ul
        className="m-0 grid list-none grid-cols-1 gap-0 border-l border-t border-[#e5e5e5] p-0 sm:grid-cols-2"
        role="list"
      >
        {recommendations.map((line) => {
          const reason = line.personalization_reason ?? line.reason;
          return (
            <li key={line.product_id} className="border-r border-b border-[#e5e5e5]">
              <article className="flex h-full flex-col gap-3 px-4 py-5 sm:px-6 sm:py-6">
                <div className="flex items-baseline justify-between gap-3">
                  <Link
                    to={`/products/${line.product_id}`}
                    prefetch="intent"
                    className="font-display text-[1.05rem] font-normal tracking-display text-ink underline decoration-ink/20 underline-offset-[0.2rem] transition-colors hover:text-accent-strong hover:decoration-accent-strong/40"
                    onMouseEnter={prefetchProductPageChunk}
                    onFocus={prefetchProductPageChunk}
                    onClick={() =>
                      trackSpec("recommendation_clicked", {
                        product_id: line.product_id,
                        category: line.category,
                        source_context: COMPLEMENT_SOURCE_CONTEXT,
                        rank: line.rank,
                        personalized: Boolean(line.personalization_reason),
                      })
                    }
                  >
                    {line.name}
                  </Link>
                  <span className="shrink-0 text-sm font-semibold tabular-nums text-ink">
                    {formatCurrency(line.price)}
                  </span>
                </div>
                {reason ? (
                  <p className={`text-[0.78rem] leading-relaxed ${tw.muted}`}>{reason}</p>
                ) : null}
                <div className="mt-auto flex flex-wrap items-center gap-3 pt-2">
                  <button
                    type="button"
                    className={tw.buttonGhost}
                    disabled={addToCart.isPending}
                    onClick={() => {
                      addToCart.mutate({ productId: line.product_id, quantity: 1 });
                      pushToast(`Added · ${line.name}`);
                      trackSpec("add_to_cart", {
                        ...fromComplementProduct(line),
                        quantity: 1,
                        source: "complement_rail",
                        rec_rank: line.rank,
                        personalized: Boolean(line.personalization_reason),
                      });
                    }}
                  >
                    Add to bag
                  </button>
                  <span className={`text-[0.65rem] uppercase tracking-ui-wide ${tw.muted}`}>
                    {line.category}
                  </span>
                </div>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

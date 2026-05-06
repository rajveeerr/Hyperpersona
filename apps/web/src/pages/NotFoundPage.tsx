import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Context } from "@/features/events/contexts";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { recommendProductsToProducts } from "@/features/recommendations/mappers";
import { resolveRailCopy } from "@/features/recommendations/railCopy";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

/**
 * RGBA WebP — **bath towel** packshot (PNGimg), not used on home hero, grid, or footer; see `UI_REFERENCE.md`.
 */
const NOT_FOUND_CUTOUT_IMG = "/not-found-product-cutout.webp";

function ProductCutoutFigure() {
  return (
    <figure className="w-full shrink-0 px-2">
      <div
        className="rounded-[max(var(--radius-inner),1rem)] border border-outline/20 bg-[radial-gradient(ellipse_92%_74%_at_50%_34%,#fdfbf7_0%,#f3eee6_52%,#e6dfd4_100%)] px-4 py-8 ring-1 ring-inset ring-white/65 sm:px-8 sm:py-10"
      >
        <div className="relative flex min-h-[min(50vh,440px)] items-center justify-center sm:min-h-[min(52vh,480px)]">
          <img
            src={NOT_FOUND_CUTOUT_IMG}
            alt=""
            width={700}
            height={1065}
            decoding="async"
            loading="lazy"
            className="mx-auto h-[min(50vh,420px)] w-auto max-w-[min(100%,260px)] object-contain drop-shadow-[0_36px_72px_rgba(34,28,23,0.14)] sm:h-[min(54vh,480px)] sm:max-w-[280px]"
          />
        </div>
      </div>
      <figcaption className="sr-only">Hanging bath towel—studio cutout on transparent background</figcaption>
    </figure>
  );
}

export function NotFoundPage() {
  const noResultsContext = Context.noResults();
  const recommendationsQuery = useQuery({
    queryKey: ["recommend", noResultsContext],
    queryFn: () => apiClient.getRecommendation(noResultsContext),
  });

  return (
    <div
      className={`${tw.stackLg} flex min-h-[min(76vh,880px)] flex-col items-center pt-8 text-center sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}
    >
      <div className="w-full max-w-md">
        <ProductCutoutFigure />
      </div>

      <header className="mx-auto mt-10 max-w-xl px-1 sm:mt-12">
        <h1 className={`${tw.storyTitle} text-balance`}>404 — Page not found</h1>
        <p className={`mx-auto mt-4 max-w-lg text-pretty text-sm leading-relaxed sm:text-[0.9375rem] ${tw.muted}`}>
          That page isn&apos;t in our store—check the address for typos, or continue shopping from the catalog. If you
          followed an old link, the collection may have changed.
        </p>
      </header>

      <div className="mx-auto mt-8 flex w-full max-w-md flex-col gap-3 sm:mx-0 sm:max-w-none sm:flex-row sm:justify-center">
        <Link to="/catalog" className={tw.buttonEditorialBag}>
          Browse catalog
        </Link>
        <Link to="/" className={tw.buttonGhost}>
          Back home
        </Link>
      </div>

      {recommendationsQuery.data && recommendationsQuery.data.products.length > 0
        ? (() => {
            const rail = resolveRailCopy(recommendationsQuery.data, {
              eyebrow: "Curated",
              headline: "While you're here, take a look at these",
              subtitle: "A few staples we'd recommend in their place.",
              modeLabel: "Trending now",
            });
            return (
              <div className="mt-12 w-full max-w-5xl text-left">
                <RecommendationRail
                  products={recommendProductsToProducts(recommendationsQuery.data.products)}
                  sourceContext={noResultsContext}
                  title={rail.headline}
                  subtitle={rail.eyebrow}
                  reason={rail.subtitle}
                  personalized={Boolean(recommendationsQuery.data.personalization_reason)}
                  modeLabel={rail.mode_label}
                  presentation="default"
                />
              </div>
            );
          })()
        : null}
    </div>
  );
}

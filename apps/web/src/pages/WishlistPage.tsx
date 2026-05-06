import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { CatalogProductGridSkeleton } from "@/features/catalog/components/CatalogSkeletons";
import { ProductGrid } from "@/features/catalog/components/ProductGrid";
import { Context } from "@/features/events/contexts";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { useWishlistStore } from "@/features/wishlist/store";
import { useWishlistHydrated } from "@/features/wishlist/useWishlistHydrated";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

/** Stroked heart only — no image plate or fill block (transparent on body canvas). */
function WishlistEmptyIllustration() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-36 w-36 shrink-0 text-ink/16 sm:h-40 sm:w-40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function WishlistPage() {
  const hydrated = useWishlistHydrated();
  const wishlistProducts = useWishlistStore((state) => state.items);
  const hasItems = wishlistProducts.length > 0;
  const wishlistContext = Context.wishlist();
  const recommendationsQuery = useQuery({
    queryKey: ["recommend", wishlistContext],
    queryFn: () => apiClient.getRecommendation(wishlistContext),
    enabled: hydrated,
  });

  return (
    <div
      className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}
    >
      <header className="max-w-3xl">
        <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Wishlist</p>
        <h1 className={`${tw.storyTitle} max-w-[26ch]`}>Saved pieces carry preference signals.</h1>
        <p className={`mt-4 max-w-xl text-pretty text-sm leading-relaxed ${tw.muted}`}>
          Same catalog grid as browse—use the heart on any tile to add here; fewer saves keeps the layout calm
          without shrinking the story.
        </p>
      </header>

      {!hydrated ? (
        <div aria-busy aria-label="Loading wishlist">
          <CatalogProductGridSkeleton count={6} />
        </div>
      ) : hasItems ? (
        <ProductGrid products={wishlistProducts} accent="Wishlisted" />
      ) : (
        <div
          className="flex flex-1 flex-col items-center justify-center gap-8 py-14 text-center sm:gap-10 sm:py-20"
          aria-live="polite"
        >
          <WishlistEmptyIllustration />
          <div className="max-w-md">
            <h2 className={`${tw.displayH2} text-2xl sm:text-[1.65rem]`}>Nothing saved yet</h2>
            <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
              Browse the catalog and tap the heart on products you care about—your wishlist feeds personalization demos
              the same way search and bag activity do.
            </p>
            <Link to="/catalog" className={`mt-8 inline-flex ${tw.buttonEditorialBag}`}>
              Browse catalog
            </Link>
          </div>
        </div>
      )}

      {hydrated && recommendationsQuery.data ? (
        <RecommendationRail
          rail={recommendationsQuery.data}
          sourceContext={wishlistContext}
          presentation="default"
        />
      ) : null}
    </div>
  );
}

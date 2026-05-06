import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { prefetchProductPageChunk } from "@/app/routeChunks";
import { CatalogProductGridSkeleton } from "@/features/catalog/components/CatalogSkeletons";
import { Context } from "@/features/events/contexts";
import { fromWishlistLine } from "@/features/events/payloads";
import { useSpecTrack } from "@/features/events/specEvents";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { recommendProductsToProducts } from "@/features/recommendations/mappers";
import { resolveRailCopy } from "@/features/recommendations/railCopy";
import { useRemoveFromWishlist, useWishlistQuery } from "@/features/wishlist/useWishlist";
import { apiClient } from "@/shared/api/client";
import type { WishlistLine } from "@/shared/api/contracts";
import { formatCurrency } from "@/shared/lib/format";
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

/**
 * Lightweight tile keyed off `WishlistLine` directly. The BE only ships
 * slug/name/image/unitPrice for wishlist rows so the catalog `ProductGrid`
 * (which depends on `Product.brand` / `freeDelivery` / `rating`) can't be
 * reused without an N+1 product fetch — not worth it for this surface.
 */
function WishlistTile({
  line,
  onRemove,
  busy,
}: {
  line: WishlistLine;
  onRemove: () => void;
  busy: boolean;
}) {
  return (
    <article className="flex flex-col items-center gap-3 border-r border-b border-[#e5e5e5] px-4 py-8 text-center sm:px-6 sm:py-10">
      <Link
        to={`/products/${line.slug}`}
        prefetch="intent"
        className="group flex w-full max-w-[18rem] flex-col items-center rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/20 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
        onMouseEnter={prefetchProductPageChunk}
        onFocus={prefetchProductPageChunk}
      >
        <div className="relative mb-5 flex w-full items-center justify-center px-1">
          <img
            src={line.image}
            alt={line.name}
            loading="lazy"
            decoding="async"
            className="h-auto w-auto max-h-[min(13rem,40svh)] max-w-full object-contain transition-[transform,filter] duration-500 ease-out motion-reduce:transition-none motion-safe:group-hover:scale-[1.02]"
            style={{ filter: "drop-shadow(0 14px 28px rgba(34, 28, 23, 0.1))" }}
          />
        </div>
        <h3 className="text-pretty text-[0.9375rem] font-medium leading-snug tracking-body text-ink">
          {line.name}
        </h3>
        <p className="mt-2 text-sm font-medium tabular-nums text-ink">
          {formatCurrency(line.unitPrice)}
        </p>
      </Link>
      <button
        type="button"
        className={`${tw.linkCommerceUnderline} text-[0.65rem]`}
        onClick={onRemove}
        disabled={busy}
      >
        Remove from wishlist
      </button>
    </article>
  );
}

export function WishlistPage() {
  const wishlistQuery = useWishlistQuery();
  const removeMutation = useRemoveFromWishlist();
  const trackSpec = useSpecTrack();

  const items = wishlistQuery.data?.items ?? [];
  const ready = wishlistQuery.isSuccess;
  const hasItems = items.length > 0;
  const wishlistContext = Context.wishlist();
  const recommendationsQuery = useQuery({
    queryKey: ["recommend", wishlistContext],
    queryFn: () => apiClient.getRecommendation(wishlistContext),
    enabled: ready,
  });

  const handleRemove = (line: WishlistLine) => {
    trackSpec("wishlist_remove", fromWishlistLine(line));
    removeMutation.mutate(line.productId);
  };

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

      {wishlistQuery.isError ? (
        <p className="text-sm text-red-800/90" role="alert">
          Could not load your wishlist. Check your connection and try again.
        </p>
      ) : !ready ? (
        <div aria-busy aria-label="Loading wishlist">
          <CatalogProductGridSkeleton count={6} />
        </div>
      ) : hasItems ? (
        <ul
          className="m-0 grid list-none grid-cols-1 gap-0 border-l border-t border-[#e5e5e5] p-0 lg:grid-cols-3"
          role="list"
        >
          {items.map((line) => (
            <li key={line.productId}>
              <WishlistTile
                line={line}
                busy={removeMutation.isPending}
                onRemove={() => handleRemove(line)}
              />
            </li>
          ))}
        </ul>
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

      {ready && recommendationsQuery.data && recommendationsQuery.data.products.length > 0
        ? (() => {
            const rail = resolveRailCopy(recommendationsQuery.data, {
              eyebrow: "Recommended",
              headline: "More to consider for your wishlist",
              subtitle: "Items in line with what you've already saved.",
              modeLabel: "More like this",
            });
            return (
              <RecommendationRail
                products={recommendProductsToProducts(recommendationsQuery.data.products)}
                sourceContext={wishlistContext}
                title={rail.headline}
                subtitle={rail.eyebrow}
                reason={rail.subtitle}
                personalized={Boolean(recommendationsQuery.data.personalization_reason)}
                modeLabel={rail.mode_label}
                presentation="default"
              />
            );
          })()
        : null}
    </div>
  );
}

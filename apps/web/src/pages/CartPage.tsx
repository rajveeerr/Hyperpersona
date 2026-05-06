import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { prefetchProductPageChunk } from "@/app/routeChunks";
import { BagSkeleton } from "@/features/cart/components/BagSkeleton";
import {
  useCartQuery,
  useRemoveFromCart,
  useUpdateCartItem,
} from "@/features/cart/useCart";
import { Context } from "@/features/events/contexts";
import { fromCartLine, variantSnapshot } from "@/features/events/payloads";
import { useSpecTrack } from "@/features/events/specEvents";
import { ComplementRail } from "@/features/recommendations/components/ComplementRail";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { recommendProductsToProducts } from "@/features/recommendations/mappers";
import { apiClient } from "@/shared/api/client";
import type { CartLine as CartLineType } from "@/shared/api/contracts";
import { formatCurrency } from "@/shared/lib/format";
import { tw } from "@/shared/ui/tw";

/** Stroked bag — matches nav bag motif, transparent on canvas (wishlist empty pattern). */
function BagEmptyIllustration() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-36 w-36 shrink-0 text-ink/16 sm:h-40 sm:w-40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M6 7h12l-1 12H7L6 7Z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M9 7V5a3 3 0 0 1 6 0v2"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const labelSerif = "font-display text-[1.05rem] font-normal tracking-display text-ink antialiased";

function CartRow({
  line,
  onRemove,
  onBumpQty,
  busy,
}: {
  line: CartLineType;
  onRemove: () => void;
  onBumpQty: (delta: number) => void;
  busy: boolean;
}) {
  return (
    <article className="flex flex-wrap items-center justify-between gap-6 border-r border-b border-[#e5e5e5] px-5 py-8 sm:px-7 sm:py-10">
      <div className="flex min-w-0 flex-1 items-center gap-5">
        <Link
          to={`/products/${line.slug}`}
          prefetch="intent"
          className="relative shrink-0 overflow-hidden rounded-lg bg-white/60 ring-1 ring-outline/25"
          onMouseEnter={prefetchProductPageChunk}
          onFocus={prefetchProductPageChunk}
        >
          <img
            src={line.image}
            alt=""
            width={160}
            height={180}
            className="size-20 object-contain sm:size-24"
            loading="lazy"
          />
        </Link>
        <div className="min-w-0 flex-1">
          <Link
            to={`/products/${line.slug}`}
            prefetch="intent"
            className={`${labelSerif} text-[1.1rem] leading-snug underline decoration-ink/20 underline-offset-[0.2rem] transition-colors hover:text-accent-strong hover:decoration-accent-strong/40`}
            onMouseEnter={prefetchProductPageChunk}
            onFocus={prefetchProductPageChunk}
          >
            {line.name}
          </Link>
          <p className="mt-2 text-sm font-medium tabular-nums text-ink">
            {formatCurrency(line.unitPrice)} each
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-5 sm:gap-6">
        <div className={tw.qtyStepper} aria-label={`Quantity for ${line.name}`}>
          <button
            type="button"
            className={tw.qtyStepperBtn}
            aria-label="Decrease quantity"
            disabled={busy || line.quantity <= 1}
            onClick={() => onBumpQty(-1)}
          >
            −
          </button>
          <span className={tw.qtyStepperValue}>{line.quantity}</span>
          <button
            type="button"
            className={tw.qtyStepperBtn}
            aria-label="Increase quantity"
            disabled={busy || line.quantity >= 20}
            onClick={() => onBumpQty(1)}
          >
            +
          </button>
        </div>
        <p className="min-w-22 text-right text-sm font-semibold tabular-nums text-ink">
          {formatCurrency(line.unitPrice * line.quantity)}
        </p>
        <button
          type="button"
          className={`${tw.linkCommerceUnderline} text-[0.65rem]`}
          onClick={onRemove}
          disabled={busy}
        >
          Remove
        </button>
      </div>
    </article>
  );
}

export function CartPage() {
  const cartQuery = useCartQuery();
  const updateMutation = useUpdateCartItem();
  const removeMutation = useRemoveFromCart();
  const trackSpec = useSpecTrack();

  const items = cartQuery.data?.items ?? [];
  const subtotal = cartQuery.data?.subtotal ?? 0;
  const hasItems = items.length > 0;
  const ready = cartQuery.isSuccess;
  const cartContext = hasItems ? Context.cartActive() : Context.cartEmpty();
  const recommendationsQuery = useQuery({
    queryKey: ["recommend", cartContext],
    queryFn: () => apiClient.getRecommendation(cartContext),
    enabled: ready,
  });

  // Frequently bought together — only meaningful when the cart has items.
  // Re-keyed by the sorted list of productIds so different cart states get
  // different cache entries (matches the BE's cache key derivation).
  const cartProductIds = items.map((line) => line.productId);
  const complementCacheKey = [...cartProductIds].sort().join(",");
  const complementQuery = useQuery({
    queryKey: ["recommend-complement", complementCacheKey],
    queryFn: () => apiClient.getComplementRecommendation(cartProductIds, 6),
    enabled: ready && hasItems,
    staleTime: 5 * 60 * 1000, // matches BE Redis TTL
  });

  const handleRemove = (line: CartLineType) => {
    const variant = variantSnapshot(line.selectedOptions ?? undefined);
    trackSpec("remove_from_cart", {
      ...fromCartLine(line),
      quantity_removed: line.quantity,
      line_total: line.unitPrice * line.quantity,
      ...(variant ? { variant } : {}),
    });
    removeMutation.mutate(line.productId);
  };

  const handleBumpQty = (line: CartLineType, delta: number) => {
    const next = Math.min(20, Math.max(1, line.quantity + delta));
    if (next === line.quantity) return;
    const variant = variantSnapshot(line.selectedOptions ?? undefined);
    // Per-click — the tracker's dedup window (`shouldDropAsDuplicate`) folds
    // bursts of identical clicks. Both the old + new quantity ship so the
    // worker can compute a stronger demand signal than just "added once".
    trackSpec("cart_quantity_changed", {
      ...fromCartLine(line),
      quantity_old: line.quantity,
      quantity_new: next,
      delta: next - line.quantity,
      ...(variant ? { variant } : {}),
    });
    updateMutation.mutate({ productId: line.productId, body: { quantity: next } });
  };

  return (
    <div className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
      <header className="max-w-3xl">
        <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Bag</p>
        <h1 className={`${tw.storyTitle} max-w-[24ch]`}>Your bag carries checkout intent for the demo.</h1>
        <p className={`mt-4 max-w-xl text-pretty text-sm leading-relaxed ${tw.muted}`}>
          Lines mirror catalog pricing and delivery flags. This is a simulated flow—no payment—so stakeholders can see
          how bag composition feeds the same tracking story as search and wishlist.
        </p>
      </header>

      {cartQuery.isError ? (
        <p className="text-sm text-red-800/90" role="alert">
          Could not load your bag. Check your connection and try again.
        </p>
      ) : !ready ? (
        <BagSkeleton rows={4} />
      ) : !hasItems ? (
        <div
          className="flex flex-1 flex-col items-center justify-center gap-8 py-14 text-center sm:gap-10 sm:py-20"
          aria-live="polite"
        >
          <BagEmptyIllustration />
          <div className="max-w-md">
            <h2 className={`${tw.displayH2} text-2xl sm:text-[1.65rem]`}>Your bag is empty</h2>
            <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
              Add pieces from the catalog or PDP—the header count updates and you can continue to checkout when you are
              ready to simulate an order.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
              <Link to="/catalog" className={tw.buttonEditorialBag}>
                Browse catalog
              </Link>
              <Link to="/" className={tw.buttonGhost}>
                Back home
              </Link>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid gap-10 lg:gap-12">
          <div className="grid gap-0 border-l border-t border-[#e5e5e5] lg:max-w-[min(100%,52rem)]">
            {items.map((line) => (
              <CartRow
                key={line.productId}
                line={line}
                busy={updateMutation.isPending || removeMutation.isPending}
                onRemove={() => handleRemove(line)}
                onBumpQty={(delta) => handleBumpQty(line, delta)}
              />
            ))}
          </div>

          <div className="grid max-w-xl gap-6 border-t border-outline/20 pt-8 sm:pt-10">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <span className={`text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Subtotal</span>
              <span className={`font-display text-2xl font-medium tabular-nums tracking-display text-ink`}>
                {formatCurrency(subtotal)}
              </span>
            </div>
            <div className="flex flex-wrap gap-4">
              <Link to="/checkout" className={tw.buttonEditorialBag}>
                Continue to checkout
              </Link>
              <Link to="/catalog" className={tw.buttonGhost}>
                Keep shopping
              </Link>
            </div>
          </div>
        </div>
      )}

      {ready && recommendationsQuery.data && recommendationsQuery.data.products.length > 0 ? (
        <RecommendationRail
          products={recommendProductsToProducts(recommendationsQuery.data.products)}
          sourceContext={cartContext}
          title={hasItems ? "Pairs well with what's in your bag" : "Worth a look while your bag is empty"}
          subtitle={hasItems ? "Recommended" : "Curated"}
          reason={recommendationsQuery.data.personalization_reason ?? undefined}
          personalized={Boolean(recommendationsQuery.data.personalization_reason)}
          presentation="default"
        />
      ) : null}

      {hasItems && complementQuery.data && complementQuery.data.recommendations.length > 0 ? (
        <ComplementRail recommendations={complementQuery.data.recommendations} />
      ) : null}
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { prefetchProductPageChunk } from "@/app/routeChunks";
import { BagSkeleton } from "@/features/cart/components/BagSkeleton";
import { useCartHydrated } from "@/features/cart/useCartHydrated";
import { type CartItem, getCartSubtotal, useCartStore } from "@/features/cart/store";
import { Context } from "@/features/events/contexts";
import { useSpecTrack } from "@/features/events/specEvents";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { apiClient } from "@/shared/api/client";
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

function CartLine({ item, onRemove, onBumpQty }: { item: CartItem; onRemove: () => void; onBumpQty: (delta: number) => void }) {
  const { product, quantity } = item;
  return (
    <article className="flex flex-wrap items-center justify-between gap-6 border-r border-b border-[#e5e5e5] px-5 py-8 sm:px-7 sm:py-10">
      <div className="flex min-w-0 flex-1 items-center gap-5">
        <Link
          to={`/products/${product.slug}`}
          prefetch="intent"
          className="relative shrink-0 overflow-hidden rounded-lg bg-white/60 ring-1 ring-outline/25"
          onMouseEnter={prefetchProductPageChunk}
          onFocus={prefetchProductPageChunk}
        >
          <img
            src={product.image}
            alt=""
            width={160}
            height={180}
            className="size-20 object-contain sm:size-24"
            loading="lazy"
          />
        </Link>
        <div className="min-w-0 flex-1">
          <Link
            to={`/products/${product.slug}`}
            prefetch="intent"
            className={`${labelSerif} text-[1.1rem] leading-snug underline decoration-ink/20 underline-offset-[0.2rem] transition-colors hover:text-accent-strong hover:decoration-accent-strong/40`}
            onMouseEnter={prefetchProductPageChunk}
            onFocus={prefetchProductPageChunk}
          >
            {product.name}
          </Link>
          <p className={`mt-1 text-xs ${tw.muted}`}>{product.brand}</p>
          <p className="mt-2 text-sm font-medium tabular-nums text-ink">{formatCurrency(product.price)} each</p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-5 sm:gap-6">
        <div className={tw.qtyStepper} aria-label={`Quantity for ${product.name}`}>
          <button
            type="button"
            className={tw.qtyStepperBtn}
            aria-label="Decrease quantity"
            disabled={quantity <= 1}
            onClick={() => onBumpQty(-1)}
          >
            −
          </button>
          <span className={tw.qtyStepperValue}>{quantity}</span>
          <button
            type="button"
            className={tw.qtyStepperBtn}
            aria-label="Increase quantity"
            disabled={quantity >= 20}
            onClick={() => onBumpQty(1)}
          >
            +
          </button>
        </div>
        <p className="min-w-22 text-right text-sm font-semibold tabular-nums text-ink">
          {formatCurrency(product.price * quantity)}
        </p>
        <button type="button" className={`${tw.linkCommerceUnderline} text-[0.65rem]`} onClick={onRemove}>
          Remove
        </button>
      </div>
    </article>
  );
}

export function CartPage() {
  const hydrated = useCartHydrated();
  const items = useCartStore((state) => state.items);
  const removeItem = useCartStore((state) => state.removeItem);
  const updateQuantity = useCartStore((state) => state.updateQuantity);
  const trackSpec = useSpecTrack();
  const subtotal = getCartSubtotal(items);
  const hasItems = items.length > 0;
  // Wait for hydration so we don't briefly request the wrong context (empty
  // before the persisted cart loads). Recommendations are gated on hydration.
  const cartContext = hasItems ? Context.cartActive() : Context.cartEmpty();
  const recommendationsQuery = useQuery({
    queryKey: ["recommend", cartContext],
    queryFn: () => apiClient.getRecommendation(cartContext),
    enabled: hydrated,
  });

  const handleRemove = (item: CartItem) => {
    trackSpec("remove_from_cart", {
      product_id: item.product.id,
      category: item.product.category,
    });
    removeItem(item.product.id);
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

      {!hydrated ? (
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
            {items.map((item) => (
              <CartLine
                key={item.product.id}
                item={item}
                onRemove={() => handleRemove(item)}
                onBumpQty={(delta) =>
                  updateQuantity(item.product.id, Math.min(20, Math.max(1, item.quantity + delta)))
                }
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

      {hydrated && recommendationsQuery.data ? (
        <RecommendationRail
          rail={recommendationsQuery.data}
          sourceContext={cartContext}
          presentation="default"
        />
      ) : null}
    </div>
  );
}

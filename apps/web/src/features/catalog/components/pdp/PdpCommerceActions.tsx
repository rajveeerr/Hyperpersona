import { Link } from "react-router-dom";

import { prefetchCatalogPageChunk } from "@/app/routeChunks";
import type { Product } from "@/shared/api/contracts";
import { formatCurrency } from "@/shared/lib/format";
import { tw } from "@/shared/ui/tw";

type PdpCommerceActionsProps = {
  product: Product;
  qty: number;
  bumpQty: (delta: number) => void;
  onAddToCart: (quantity: number, variantContext?: Record<string, string>) => void;
  variantContext: Record<string, string>;
  wishlisted: boolean;
  onWishlistToggle: () => void;
};

export function PdpCommerceActions({
  product,
  qty,
  bumpQty,
  onAddToCart,
  variantContext,
  wishlisted,
  onWishlistToggle,
}: PdpCommerceActionsProps) {
  return (
    <div className="mt-auto flex min-h-0 flex-col gap-5 border-t border-outline/15 pt-8">
      <div className="flex min-w-0 flex-wrap items-center gap-3 sm:gap-4">
        <div className={tw.qtyStepper} aria-label="Quantity">
          <button type="button" className={tw.qtyStepperBtn} onClick={() => bumpQty(-1)} aria-label="Decrease quantity">
            −
          </button>
          <span className={tw.qtyStepperValue}>{qty}</span>
          <button type="button" className={tw.qtyStepperBtn} onClick={() => bumpQty(1)} aria-label="Increase quantity">
            +
          </button>
        </div>
        <button
          type="button"
          className={`${tw.buttonEditorialBag} min-w-0 flex-1 sm:max-w-md sm:flex-initial`}
          onClick={() => onAddToCart(qty, variantContext)}
        >
          Add to bag — {formatCurrency(product.price * qty)}
        </button>
      </div>

      <nav
        className="flex w-full flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-x-4"
        aria-label="More actions"
      >
        <button type="button" className={tw.linkCommerceUnderline} onClick={onWishlistToggle}>
          {wishlisted ? "Remove from saved" : "Save for later"}
        </button>
        <Link to="/checkout" className={tw.linkCommerceUnderline}>
          Checkout →
        </Link>
        <Link
          to="/catalog"
          prefetch="intent"
          className={tw.linkCommerceUnderline}
          onMouseEnter={prefetchCatalogPageChunk}
          onFocus={prefetchCatalogPageChunk}
        >
          Back to catalog →
        </Link>
      </nav>
    </div>
  );
}

import { Link } from "react-router-dom";

import { prefetchProductPageChunk } from "@/app/routeChunks";
import { productSnapshot } from "@/features/events/payloads";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import type { Product } from "@/shared/api/contracts";
import { formatCurrency } from "@/shared/lib/format";
import { tw } from "@/shared/ui/tw";

type ProductCardProps = {
  product: Product;
  /**
   * Optional micro-label (recommendation rails, search ranking) — same tile chrome as `/catalog`;
   * omit on dense listings when the page title already states context.
   */
  accent?: string;
  /**
   * Fires before navigation alongside the built-in tile-click events. Used by
   * `RecommendationRail` to emit `recommendation_clicked` with its source
   * context. The card's own tracking (`product_click`, `product_tile_clicked`)
   * still fires regardless.
   */
  onClick?: (product: Product) => void;
};

/** Caps hero crop height so portrait SKUs don’t push title/price down; `object-contain` keeps native ratio. */
const catalogImageMax =
  "max-h-[min(13.5rem,min(52vw,40svh))] sm:max-h-[min(14.5rem,min(44vw,38svh))] lg:max-h-[min(15.5rem,min(30vw,36svh))]";

/**
 * Single product tile treatment site-wide (column/row dividers live on `ProductGrid`; no tile fill).
 * Editorial **New collection** (`EditorialNewCollectionSection`) stays bespoke lookbook markup.
 */
export function ProductCard({ product, accent, onClick }: ProductCardProps) {
  const track = useTrackEvent();

  const trackClick = () => {
    track({
      event_type: "product_tile_clicked",
      payload: {
        ...productSnapshot(product),
        // Keep camelCase aliases the BE has been seeing, so any worker
        // already keyed off `productId`/`slug` keeps working alongside the
        // new snake_case snapshot fields.
        productId: product.id,
        slug: product.slug,
        source: "grid",
      },
      consent_scope: ["analytics", "personalization"],
    });
    onClick?.(product);
  };

  return (
    <article className="flex flex-col items-center text-center">
      <Link
        to={`/products/${product.slug}`}
        prefetch="intent"
        className="group flex w-full max-w-[20rem] flex-col items-center rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/20 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
        onClick={trackClick}
        onMouseEnter={prefetchProductPageChunk}
        onFocus={prefetchProductPageChunk}
      >
        {accent ? (
          <span
            className={`mb-3 block text-center text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-accent-strong`}
          >
            {accent}
          </span>
        ) : null}
        <div className="relative mb-6 flex min-h-29 w-full max-w-[18rem] items-center justify-center px-1 sm:min-h-32 sm:px-2">
          <img
            src={product.image}
            alt={product.name}
            loading="lazy"
            decoding="async"
            width={900}
            height={1012}
            sizes="(max-width: 640px) 72vw, (max-width: 1024px) 34vw, 320px"
            className={`h-auto w-auto max-w-full object-contain ${catalogImageMax} transition-[transform,filter] duration-500 ease-out motion-reduce:transition-none motion-safe:group-hover:scale-[1.02]`}
            style={{
              filter: "drop-shadow(0 18px 36px rgba(34, 28, 23, 0.1))",
            }}
          />
        </div>
        <h3 className="text-pretty text-[0.9375rem] font-medium leading-snug tracking-body text-ink">{product.name}</h3>
        <p className={`mt-1.5 text-xs ${tw.muted}`}>{product.brand}</p>
        <p className="mt-2 text-sm font-medium tabular-nums tracking-body text-ink">{formatCurrency(product.price)}</p>
        <p className={`mt-1.5 flex flex-wrap items-center justify-center gap-x-1.5 text-[0.6875rem] ${tw.muted}`}>
          <span className="tabular-nums">{product.rating.toFixed(1)} rating</span>
          {product.freeDelivery ? (
            <>
              <span aria-hidden>·</span>
              <span>Free delivery</span>
            </>
          ) : null}
          {product.inventoryStatus !== "in-stock" ? (
            <>
              <span aria-hidden>·</span>
              <span className="capitalize">{product.inventoryStatus.replaceAll("-", " ")}</span>
            </>
          ) : null}
        </p>
      </Link>
    </article>
  );
}

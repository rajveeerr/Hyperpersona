import { Link } from "react-router-dom";

import { formatCategoryLabel } from "@/features/catalog/components/pdp/pdpShared";
import type { Product } from "@/shared/api/contracts";
import { formatCurrency } from "@/shared/lib/format";
import { StarRating } from "@/shared/ui/StarRating";
import { tw } from "@/shared/ui/tw";

type PdpProductSummaryProps = {
  product: Product;
  vertical: string;
  pctOff: number | null;
};

export function PdpProductSummary({ product, vertical, pctOff }: PdpProductSummaryProps) {
  return (
    <header className="min-w-0">
      <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>
        {product.brand}
        {product.department ? (
          <>
            {" "}
            · <span className="normal-case">{product.department}</span>
          </>
        ) : null}
      </p>
      <h1 id="pdp-title" className={`${tw.displayProductTitle} text-[clamp(2rem,4vw,3.25rem)]`}>
        {product.name}
      </h1>
      <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="text-[clamp(1.2rem,2.2vw,1.65rem)] font-medium tabular-nums tracking-tight text-ink">
          {formatCurrency(product.price)}
        </p>
        {product.compareAt != null && product.compareAt > product.price ? (
          <>
            <span className={`text-base font-normal line-through ${tw.muted}`}>{formatCurrency(product.compareAt)}</span>
            {pctOff != null ? (
              <span className="rounded-pill border border-success/35 bg-success/10 px-2.5 py-0.5 text-[0.75rem] font-semibold text-success">
                {pctOff}% off
              </span>
            ) : null}
          </>
        ) : null}
      </div>
      <p className={`mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.8125rem] tracking-[0.02em] ${tw.muted}`}>
        <span className="inline-flex items-center gap-1.5">
          <StarRating rating={product.rating} className="text-[0.78rem] sm:text-[0.82rem]" />
          <span className="tabular-nums font-medium text-ink/88">{product.rating.toFixed(1)}</span>
        </span>
        <span aria-hidden className="text-ink/35">
          ·
        </span>
        <span>{product.reviewCount} reviews</span>
        <span aria-hidden className="text-ink/35">
          ·
        </span>
        <span className="capitalize">{product.inventoryStatus.replaceAll("-", " ")}</span>
        <span aria-hidden className="text-ink/35">
          ·
        </span>
        <span className="capitalize">{vertical}</span>
      </p>
      <p className={`mt-4 max-w-xl text-pretty text-sm leading-relaxed sm:text-[0.9375rem] ${tw.muted}`}>
        {product.description}
      </p>
      <dl
        className={`mt-6 grid gap-3 border-t border-outline/12 pt-6 text-[0.8125rem] sm:grid-cols-2 sm:gap-x-8 ${tw.muted}`}
      >
        <div>
          <dt className="text-[0.65rem] font-semibold uppercase tracking-ui-wide text-ink/55">SKU</dt>
          <dd className="mt-1 font-medium tabular-nums tracking-body text-ink/90">{product.id}</dd>
        </div>
        <div>
          <dt className="text-[0.65rem] font-semibold uppercase tracking-ui-wide text-ink/55">Category</dt>
          <dd className="mt-1">
            <Link
              to={`/catalog?category=${encodeURIComponent(product.category)}`}
              className="font-medium text-ink underline decoration-ink/25 underline-offset-[0.2rem] transition-colors hover:text-accent-strong"
            >
              {formatCategoryLabel(product.category)}
            </Link>
          </dd>
        </div>
      </dl>
      <ul
        className="mt-5 flex flex-col gap-2.5 border-t border-outline/10 pt-5 text-[0.75rem] leading-snug text-ink/85"
        aria-label="Service notes"
      >
        <li className="flex max-w-[min(100%,42rem)] gap-2.5">
          <span className="mt-[0.42em] size-1.5 shrink-0 rounded-full bg-accent-strong" aria-hidden />
          <span>
            {product.freeDelivery ? "Free delivery on this SKU." : "Standard delivery — fee shown at checkout."}
          </span>
        </li>
        <li className="flex max-w-[min(100%,42rem)] gap-2.5">
          <span className="mt-[0.42em] size-1.5 shrink-0 rounded-full bg-accent-strong" aria-hidden />
          <span>Editorial imagery and specs stay in sync with the catalog API.</span>
        </li>
      </ul>
    </header>
  );
}

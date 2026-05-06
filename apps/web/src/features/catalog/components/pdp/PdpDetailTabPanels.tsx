import type { Product } from "@/shared/api/contracts";
import { StarRating } from "@/shared/ui/StarRating";
import { tw } from "@/shared/ui/tw";

import {
  showStylingTab,
  specDd,
  specDt,
  specRow,
  type DetailTab,
} from "@/features/catalog/components/pdp/pdpShared";

type PdpDetailTabPanelsProps = {
  product: Product;
  vertical: string;
  tab: DetailTab;
  specLines: string[];
};

/** Tab panel bodies only — toolbar lives in `PdpTabbedDetails` for clearer composition (Vercel: smaller leaf components). */
export function PdpDetailTabPanels({ product, vertical, tab, specLines }: PdpDetailTabPanelsProps) {
  return (
    <>
      {tab === "description" ? (
        <div className="max-w-3xl">
          <h2 className={`${tw.displayH2} text-2xl sm:text-3xl`}>Product details</h2>
          <div className={`mt-4 space-y-4 text-sm leading-relaxed sm:text-[0.9375rem] ${tw.muted}`}>
            <p className="text-pretty text-ink/90">{product.longDescription ?? product.description}</p>
          </div>
          <dl className="mt-8 border-t border-outline/15">
            {product.dimensions?.display ? (
              <div className={specRow}>
                <dt className={specDt}>Package dimensions</dt>
                <dd className={specDd}>{product.dimensions.display}</dd>
              </div>
            ) : null}
            {specLines.length > 0 ? (
              <div className={specRow}>
                <dt className={specDt}>Specification</dt>
                <dd className={specDd}>{specLines.join(", ")}</dd>
              </div>
            ) : null}
            {product.dateFirstAvailable ? (
              <div className={specRow}>
                <dt className={specDt}>Date first available</dt>
                <dd className={specDd}>{product.dateFirstAvailable}</dd>
              </div>
            ) : null}
            {product.department ? (
              <div className={specRow}>
                <dt className={specDt}>Department</dt>
                <dd className={specDd}>{product.department}</dd>
              </div>
            ) : null}
          </dl>
        </div>
      ) : null}

      {tab === "styling" && showStylingTab(product.vertical) ? (
        <div className="max-w-3xl">
          <h2 className={`${tw.displayH2} text-2xl sm:text-3xl`}>Styling ideas</h2>
          <p className={`mt-4 text-pretty text-sm leading-relaxed sm:text-[0.9375rem] ${tw.muted}`}>
            Outfit and layer pairings for apparel—grounded in tags and how this piece reads in editorial shoots.
            Non-apparel SKUs use Highlights instead so category copy stays truthful.
          </p>
          {(product.tags?.length ?? 0) > 0 ? (
            <ul className={`${tw.chipList} mt-6`} aria-label="Style tags">
              {product.tags!.map((tag) => (
                <li key={tag} className={tw.chip}>
                  {tag}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {tab === "reviews" ? (
        <div id="pdp-reviews" className="max-w-3xl scroll-mt-24">
          <h2 className={`${tw.displayH2} text-2xl sm:text-3xl`}>Reviews</h2>
          <p
            className={`mt-4 flex flex-wrap items-start gap-x-2 gap-y-2 text-sm leading-relaxed sm:text-[0.9375rem] ${tw.muted}`}
          >
            <StarRating rating={product.rating} className="mt-0.5 shrink-0 text-[0.85rem]" />
            <span>
              {product.reviewCount} reviews · average {product.rating.toFixed(1)}. Full review threads, load more,
              and helpful votes ship with the reviews module; telemetry contracts are already in{" "}
              <code className="rounded bg-white/60 px-1 py-0.5 text-xs text-ink/80">API_REQUIREMENTS.md</code>.
            </span>
          </p>
        </div>
      ) : null}

      {tab === "highlights" ? (
        <div className="max-w-3xl">
          <h2 className={`${tw.displayH2} text-2xl sm:text-3xl`}>Highlights</h2>
          {!showStylingTab(product.vertical) && (product.tags?.length ?? 0) > 0 ? (
            <>
              <p className={`mt-4 text-sm leading-relaxed sm:text-[0.9375rem] ${tw.muted}`}>
                Merchandising tags for this {vertical} SKU (replaces apparel-only “Styling ideas”).
              </p>
              <ul className={`${tw.chipList} mt-4`} aria-label="Product tags">
                {product.tags!.map((tag) => (
                  <li key={tag} className={tw.chip}>
                    {tag}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {product.badges.length > 0 ? (
            <ul className={`${tw.chipList} mt-6`} aria-label="Badges">
              {product.badges.map((badge) => (
                <li key={badge} className={tw.chip}>
                  {badge}
                </li>
              ))}
            </ul>
          ) : null}
          <ul className={`mt-6 space-y-2 text-sm leading-relaxed text-ink/90 sm:text-[0.9375rem]`}>
            {product.features.map((line) => (
              <li key={line} className="flex gap-2">
                <span className="mt-2 size-1 shrink-0 rounded-full bg-accent" aria-hidden />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}

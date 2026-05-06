import { Link } from "react-router-dom";

import { tw } from "@/shared/ui/tw";

/** Warm-neutral studio packshot — RGBA WebP, canvas shows through (`UI_REFERENCE.md`). */
export const CATALOG_FILTER_EMPTY_CUTOUT = "/catalog-filter-empty-cutout.webp";

type ListingEmptyFilteredProps = {
  /** True when department or delivery narrowing is active (clearable without leaving browse scope). */
  hasFacetFilters: boolean;
  /** True when a catalog category slug is selected (can widen to all categories). */
  hasCategoryScope?: boolean;
  onClearFacetFilters: () => void;
  /** Catalog only — widens to “All categories”. Omit on search. */
  onClearCategoryScope?: () => void;
  browseCatalogHref?: string;
  browseCatalogLabel?: string;
  headline?: string;
  body?: string;
};

export function ListingEmptyFiltered({
  hasFacetFilters,
  hasCategoryScope = false,
  onClearFacetFilters,
  onClearCategoryScope,
  browseCatalogHref = "/catalog",
  browseCatalogLabel = "Browse catalog",
  headline = "No products match these filters",
  body = "Widen department or delivery, choose another category, or continue browsing—the editorial grid will fill in again.",
}: ListingEmptyFilteredProps) {
  return (
    <div
      className="flex flex-1 flex-col items-center gap-10 py-12 sm:gap-12 sm:py-16"
      aria-live="polite"
    >
      <div className="relative w-full max-w-[min(100%,18rem)]">
        <img
          src={CATALOG_FILTER_EMPTY_CUTOUT}
          alt=""
          className="mx-auto h-auto w-full max-w-[min(100%,14rem)] drop-shadow-[0_24px_48px_rgba(34,28,23,0.12)]"
          width={800}
          height={1200}
          loading="lazy"
          decoding="async"
        />
        <div
          className="pointer-events-none absolute -inset-4 -z-10 rounded-[2.5rem] bg-[radial-gradient(ellipse_at_40%_25%,rgba(34,28,23,0.05),transparent_58%)]"
          aria-hidden
        />
      </div>
      <div className="max-w-md text-center">
        <h2 className={`${tw.displayH2} text-2xl sm:text-[1.65rem]`}>{headline}</h2>
        <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>{body}</p>
        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center sm:gap-4">
          {hasFacetFilters ? (
            <button type="button" className={`inline-flex ${tw.buttonEditorialBag}`} onClick={onClearFacetFilters}>
              Clear filters
            </button>
          ) : null}
          {!hasFacetFilters && hasCategoryScope && onClearCategoryScope ? (
            <button type="button" className={`inline-flex ${tw.buttonEditorialBag}`} onClick={onClearCategoryScope}>
              View all categories
            </button>
          ) : null}
          <Link to={browseCatalogHref} className={`inline-flex ${tw.buttonGhost}`}>
            {browseCatalogLabel}
          </Link>
        </div>
      </div>
    </div>
  );
}

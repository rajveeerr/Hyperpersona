import type { CatalogFacetGroup, Category } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

type CatalogToolbarProps = {
  categories: Category[];
  /** When false, the category control is omitted (e.g. `/search` where scope is the query string). */
  showCategory?: boolean;
  activeCategory: string;
  activeSort: string;
  /** When product list is still fetching, avoid showing “0 results” in the summary line. */
  resultsLoading?: boolean;
  total: number;
  /** Count matching filters before pagination (same as API `total`). */
  totalFiltered?: number;
  page?: number;
  pageSize?: number;
  activeVertical?: string;
  freeDeliveryOnly?: boolean;
  facets?: CatalogFacetGroup[];
  onCategoryChange: (category: string) => void;
  onSortChange: (sort: string) => void;
  onVerticalChange?: (vertical: string) => void;
  onFreeDeliveryToggle?: (only: boolean) => void;
};

const labelSerif = "font-display text-[1.05rem] font-normal tracking-display text-ink antialiased";

const dashedSelect =
  "w-full cursor-pointer appearance-none rounded-pill border border-dashed border-ink/35 bg-transparent py-2.5 pl-4 pr-10 text-[0.8125rem] font-medium tracking-body text-ink outline-none transition-colors hover:border-ink/50 focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-ink/12";

/** Idle — dashed outline only (never use `text-white` here). */
const deptPillIdle =
  "min-h-9 min-w-[2.75rem] cursor-pointer rounded-pill border border-dashed border-ink/40 bg-white/70 px-3.5 py-2 text-[0.75rem] font-medium leading-snug text-ink shadow-none transition-[background-color,border-color,box-shadow,color] hover:border-ink/55 hover:bg-white";

/**
 * Selected — cream + ink ring (same vocabulary as PDP `optionSelected` / `tw.buttonEditorialBag`), not solid black.
 */
const deptPillSelected =
  "min-h-9 min-w-[2.75rem] cursor-pointer rounded-pill border border-ink/30 bg-surface-strong px-3.5 py-2 text-center text-[0.75rem] font-semibold leading-snug text-ink shadow-[0_6px_18px_rgba(34,28,23,0.06)] ring-1 ring-inset ring-white/65 transition-[background-color,border-color,box-shadow] hover:border-ink/40";

export const CatalogToolbar = ({
  categories,
  showCategory = true,
  activeCategory,
  activeSort,
  resultsLoading = false,
  total,
  totalFiltered,
  page = 1,
  pageSize = 12,
  activeVertical = "",
  freeDeliveryOnly = false,
  facets,
  onCategoryChange,
  onSortChange,
  onVerticalChange,
  onFreeDeliveryToggle,
}: CatalogToolbarProps) => {
  const verticalFacet = facets?.find((f) => f.id === "vertical");
  const freeFacet = facets?.find((f) => f.id === "freeDelivery");
  const freeCount = freeFacet?.values?.find((v) => v.value === "true")?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const showingFrom = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const showingTo = Math.min(page * pageSize, totalFiltered ?? total);

  return (
    <div className="grid gap-8 border-b border-outline/15 pb-8 sm:gap-10 sm:pb-10">
      <div
        className={`flex flex-col gap-8 sm:flex-row sm:items-end sm:gap-10 ${showCategory ? "sm:justify-between" : "sm:justify-start"}`}
      >
        {showCategory ? (
          <div className="grid w-full max-w-md gap-0.5">
            <label htmlFor="catalog-category" className={labelSerif}>
              Category
            </label>
            <div className="relative mt-2 inline-block w-full max-w-[min(100%,14rem)]">
              <select
                id="catalog-category"
                value={activeCategory}
                onChange={(e) => onCategoryChange(e.target.value)}
                className={dashedSelect}
              >
                <option value="">All categories</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.slug}>
                    {category.name}
                  </option>
                ))}
              </select>
              <span
                className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-[0.6rem] leading-none text-ink/45"
                aria-hidden
              >
                ▾
              </span>
            </div>
          </div>
        ) : null}

        <div className={`grid w-full max-w-xs gap-0.5 ${showCategory ? "sm:text-right" : ""}`}>
          <label
            htmlFor="catalog-sort"
            className={`${labelSerif} ${showCategory ? "sm:ml-auto sm:max-w-[14rem]" : ""}`}
          >
            Sort by
          </label>
          <div
            className={`relative mt-2 inline-block w-full max-w-[min(100%,14rem)] ${showCategory ? "sm:ml-auto" : ""}`}
          >
            <select
              id="catalog-sort"
              value={activeSort}
              onChange={(e) => onSortChange(e.target.value)}
              className={dashedSelect}
            >
              <option value="featured">Featured</option>
              <option value="price-asc">Price: low to high</option>
              <option value="price-desc">Price: high to low</option>
              <option value="rating">Top rated</option>
            </select>
            <span
              className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-[0.6rem] leading-none text-ink/45"
              aria-hidden
            >
              ▾
            </span>
          </div>
        </div>
      </div>

      {onVerticalChange && verticalFacet?.values?.length ? (
        <div className="grid gap-3" aria-label="Department filters">
          <span className={`text-[0.65rem] font-semibold uppercase tracking-ui-wide ${tw.muted}`}>Department</span>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={activeVertical === "" ? deptPillSelected : deptPillIdle}
              aria-pressed={activeVertical === ""}
              onClick={() => onVerticalChange("")}
            >
              All
            </button>
            {verticalFacet.values?.map((v) => {
              const selected = activeVertical === v.value;
              return (
                <button
                  key={v.value}
                  type="button"
                  className={selected ? deptPillSelected : deptPillIdle}
                  aria-pressed={selected}
                  onClick={() => onVerticalChange(v.value)}
                >
                  {v.label}
                  <span className={selected ? "font-medium text-ink/50" : "text-ink/45"}>
                    {" "}
                    ({v.count})
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {onFreeDeliveryToggle ? (
        <div className="grid gap-3" role="presentation">
          <span className={`text-[0.65rem] font-semibold uppercase tracking-ui-wide ${tw.muted}`}>Delivery</span>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              role="switch"
              aria-checked={freeDeliveryOnly}
              aria-label={
                freeDeliveryOnly
                  ? "Free delivery filter on. Click to show all items."
                  : "Free delivery filter off. Click to show only items with free delivery."
              }
              className={`max-w-full text-pretty ${freeDeliveryOnly ? deptPillSelected : deptPillIdle}`}
              onClick={() => onFreeDeliveryToggle(!freeDeliveryOnly)}
            >
              Free delivery only
              <span className={freeDeliveryOnly ? "font-medium text-ink/50" : "text-ink/45"}>
                {" "}
                ({freeCount})
              </span>
            </button>
          </div>
        </div>
      ) : null}

      <p className={`text-[0.8125rem] leading-relaxed ${tw.muted}`}>
        {resultsLoading
          ? "Loading results…"
          : total === 0
            ? "No products match these filters."
            : `Showing ${showingFrom}–${showingTo} of ${totalFiltered ?? total} · page ${page} / ${totalPages}`}
      </p>
    </div>
  );
};

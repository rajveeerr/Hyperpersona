import {
  catalogGridCellEdgeClass,
  catalogGridShellDivClass,
  catalogSuggestionsCell,
  catalogTileCell,
} from "@/features/catalog/components/ProductGrid";
import { tw } from "@/shared/ui/tw";

const pulse = "animate-pulse rounded-md bg-ink/[0.06]";

export function CatalogToolbarSkeleton() {
  return (
    <div className="grid gap-6 border-b border-outline/15 pb-8" aria-hidden>
      <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="grid gap-2">
          <div className={`h-5 w-24 ${pulse}`} />
          <div className={`h-10 w-full max-w-56 rounded-pill ${pulse}`} />
        </div>
        <div className="grid gap-2">
          <div className={`h-5 w-20 ${pulse}`} />
          <div className={`h-10 w-full max-w-48 rounded-pill ${pulse}`} />
        </div>
      </div>
      <div className={`h-4 w-64 max-w-full ${pulse}`} />
    </div>
  );
}

/** Department + delivery facet rows while product facets reload (matches `CatalogToolbar` pill rhythm). */
export function CatalogFacetFiltersSkeleton() {
  return (
    <div className="grid gap-8 sm:gap-10" aria-hidden aria-busy>
      <div className="grid gap-3">
        <div className={`h-3 w-28 ${pulse}`} />
        <div className="flex flex-wrap gap-2">
          <div className={`h-9 w-14 shrink-0 rounded-pill ${pulse}`} />
          <div className={`h-9 w-44 max-w-[min(100%,11rem)] rounded-pill ${pulse}`} />
          <div className={`h-9 w-40 max-w-[min(100%,10rem)] rounded-pill ${pulse}`} />
          <div className={`h-9 w-36 max-w-[min(100%,9rem)] rounded-pill ${pulse}`} />
          <div className={`h-9 w-32 max-w-[min(100%,8rem)] rounded-pill ${pulse}`} />
        </div>
      </div>
      <div className="grid gap-3">
        <div className={`h-3 w-24 ${pulse}`} />
        <div className={`h-9 w-52 max-w-full rounded-pill ${pulse}`} />
      </div>
    </div>
  );
}

/** Search results toolbar: sort + facet rows without category (matches `CatalogToolbar` rhythm). */
export function SearchFiltersToolbarSkeleton() {
  return (
    <div className="grid gap-6 border-b border-outline/15 pb-8 sm:gap-8" aria-hidden>
      <div className="grid w-full max-w-xs gap-2 sm:justify-self-start">
        <div className={`h-5 w-20 ${pulse}`} />
        <div className={`h-10 w-full max-w-[min(100%,14rem)] rounded-pill ${pulse}`} />
      </div>
      <div className="flex flex-wrap gap-2">
        <div className={`h-9 w-14 rounded-pill ${pulse}`} />
        <div className={`h-9 w-36 rounded-pill ${pulse}`} />
        <div className={`h-9 w-32 rounded-pill ${pulse}`} />
      </div>
      <div className={`h-9 max-w-xs rounded-pill ${pulse}`} />
      <div className={`h-4 w-72 max-w-full ${pulse}`} />
    </div>
  );
}

function SkeletonCatalogCard() {
  return (
    <div className="flex w-full max-w-[20rem] flex-col items-center px-2 py-2" aria-hidden>
      <div
        className={`mb-6 h-[min(13.5rem,min(52vw,40svh))] w-full max-w-[18rem] sm:h-[min(14.5rem,min(44vw,38svh))] lg:h-[min(15.5rem,min(30vw,36svh))] ${pulse}`}
      />
      <div className={`mb-2 h-4 w-[85%] ${pulse}`} />
      <div className={`h-3 w-16 ${pulse}`} />
    </div>
  );
}

export function CatalogProductGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className={catalogGridShellDivClass} aria-busy aria-label="Loading products">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={`${catalogTileCell} ${catalogGridCellEdgeClass}`}>
          <SkeletonCatalogCard />
        </div>
      ))}
    </div>
  );
}

/** PDP “suggested next” rails while recommendations load. */
export function PdpSuggestionsRailsSkeleton() {
  return (
    <div className="grid gap-14 sm:gap-16" aria-busy aria-label="Loading suggestions">
      {[0, 1].map((i) => (
        <div key={i} className="grid gap-5">
          <div className={`h-4 w-56 max-w-full ${pulse}`} />
          <div className={`h-3 w-full max-w-xl ${pulse}`} />
          <div className={`mt-4 ${catalogGridShellDivClass}`}>
            {[0, 1, 2].map((j) => (
              <div key={j} className={`${catalogSuggestionsCell} ${catalogGridCellEdgeClass}`}>
                <div className="flex w-full max-w-[20rem] flex-col items-center gap-3">
                  <div
                    className={`h-[min(12rem,min(48vw,36svh))] w-full max-w-[16rem] sm:h-[min(13rem,min(40vw,34svh))] lg:h-[min(14rem,min(26vw,32svh))] ${pulse}`}
                  />
                  <div className={`h-3 w-[80%] ${pulse}`} />
                  <div className={`h-3 w-12 ${pulse}`} />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ProductDetailSkeleton() {
  return (
    <div
      className={`${tw.editorialBreakout} border-b border-outline/15 bg-[radial-gradient(ellipse_82%_78%_at_50%_36%,#fdfbf7_0%,#f5f2ed_48%,#e9e3da_100%)]`}
      aria-busy
      aria-label="Loading product"
    >
      <div className={`${tw.layoutFrame} py-8 sm:py-10 lg:py-12`}>
        <div className={`mb-8 h-4 w-48 max-w-[60%] ${pulse}`} />
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1.08fr)_minmax(0,1fr)] lg:gap-x-12">
          <div className={`min-h-[min(52vh,420px)] w-full rounded-xl ${pulse}`} />
          <div className="grid gap-6">
            <div className={`h-10 w-full max-w-md ${pulse}`} />
            <div className={`h-8 w-40 ${pulse}`} />
            <div className={`h-24 w-full max-w-xl ${pulse}`} />
            <div className={`h-32 w-full rounded-xl ${pulse}`} />
            <div className="flex gap-2 pt-4">
              <div className={`h-10 w-24 rounded-pill ${pulse}`} />
              <div className={`h-10 w-24 rounded-pill ${pulse}`} />
              <div className={`h-10 w-28 rounded-pill ${pulse}`} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

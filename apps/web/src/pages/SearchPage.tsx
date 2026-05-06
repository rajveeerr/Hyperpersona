import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { CatalogToolbar } from "@/features/catalog/components/CatalogToolbar";
import {
  CatalogProductGridSkeleton,
  SearchFiltersToolbarSkeleton,
} from "@/features/catalog/components/CatalogSkeletons";
import { ProductGrid } from "@/features/catalog/components/ProductGrid";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import { SearchInsightPanel, SearchInsightPanelSkeleton } from "@/features/search/components/SearchInsightPanel";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

/** Editorial still life (warm neutrals) — [Unsplash License](https://unsplash.com/license). Photographer: Spacejoy / Unsplash. */
const SEARCH_NO_RESULTS_IMAGE =
  "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=960&q=82";

function buildSearchListParams(args: {
  q: string;
  page: string;
  sort: string;
  vertical: string;
  freeDelivery: string;
}) {
  const p = new URLSearchParams();
  p.set("q", args.q);
  p.set("page", args.page || "1");
  p.set("pageSize", "12");
  if (args.sort) {
    p.set("sort", args.sort);
  }
  if (args.vertical) {
    p.set("vertical", args.vertical);
  }
  if (args.freeDelivery === "true") {
    p.set("freeDelivery", "true");
  }
  return `?${p.toString()}`;
}

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const track = useTrackEvent();
  /** Trimmed — whitespace-only `q` does not run search (queries stay disabled). */
  const q = (params.get("q") ?? "").trim();
  const page = params.get("page") ?? "1";
  const sort = params.get("sort") ?? "featured";
  const vertical = params.get("vertical") ?? "";
  const freeDelivery = params.get("freeDelivery") === "true" ? "true" : "";

  const listParams = useMemo(
    () => buildSearchListParams({ q, page, sort, vertical, freeDelivery }),
    [q, page, sort, vertical, freeDelivery],
  );

  const query = useQuery({
    queryKey: ["search", q, page, sort, vertical, freeDelivery],
    queryFn: () => apiClient.searchProducts(listParams),
    enabled: q.length > 0,
  });

  const explanationsQuery = useQuery({
    queryKey: ["explanations", q],
    queryFn: apiClient.getExplanations,
    enabled: q.length > 0,
  });

  const productsBusy = Boolean(q) && (query.isPending || query.isLoading);
  const pageNum = Math.max(1, Number(page || "1"));
  const pageSize = query.data?.pageSize ?? 12;
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const setPage = (nextPage: number) => {
    const next = new URLSearchParams(params);
    if (nextPage <= 1) {
      next.delete("page");
    } else {
      next.set("page", String(nextPage));
    }
    setParams(next);
  };

  const updateSort = (nextSort: string) => {
    const next = new URLSearchParams(params);
    next.set("sort", nextSort);
    next.delete("page");
    setParams(next);
    track({
      customer_id: "demo-customer-1",
      event_type: "sort_changed",
      payload: { sort: nextSort, surface: "search", q },
      consent_scope: ["analytics", "personalization"],
    });
  };

  const updateVertical = (nextVertical: string) => {
    const next = new URLSearchParams(params);
    if (nextVertical) {
      next.set("vertical", nextVertical);
    } else {
      next.delete("vertical");
    }
    next.delete("page");
    setParams(next);
    track({
      customer_id: "demo-customer-1",
      event_type: "filter_change",
      payload: { filter: "vertical", value: nextVertical || "all", surface: "search", q },
      consent_scope: ["analytics", "personalization"],
    });
  };

  const updateFreeDelivery = (only: boolean) => {
    const next = new URLSearchParams(params);
    if (only) {
      next.set("freeDelivery", "true");
    } else {
      next.delete("freeDelivery");
    }
    next.delete("page");
    setParams(next);
    track({
      customer_id: "demo-customer-1",
      event_type: "filter_change",
      payload: { filter: "freeDelivery", value: only, surface: "search", q },
      consent_scope: ["analytics", "personalization"],
    });
  };

  const noopCategory = () => {};

  const shellMin =
    q.length > 0
      ? "min-h-[min(76vh,880px)]"
      : "min-h-[min(52vh,560px)]";

  return (
    <div className={`${tw.stackLg} ${shellMin} pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
      <header className="max-w-3xl">
        <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Search</p>
        <h1 className={`${tw.storyTitle} max-w-[22ch]`}>
          {q ? `Results for “${q}”` : "Search the catalog"}
        </h1>
        {q ? (
          <p className={`mt-4 max-w-2xl text-sm leading-relaxed ${tw.muted}`}>
            Ranking reflects your consent scope and recent signals the explainability panel below is how HyperPersona
            surfaces why a result set is personalized or generic for this query.
          </p>
        ) : (
          <p className={`mt-4 max-w-2xl text-sm leading-relaxed ${tw.muted}`}>
            Submit a query from the header to see catalog search with the same grid, filters, and pagination as browse.
          </p>
        )}
      </header>

      {query.isError ? (
        <p className="text-sm text-red-800/90" role="alert">
          Could not load search results. Check your connection and try again.
        </p>
      ) : null}

      {!q ? (
        <p className={`text-sm ${tw.muted}`}>Search for products to see ranking behavior.</p>
      ) : (
        <div className={`${tw.stackLg} flex flex-1 flex-col`}>
          {query.isError ? null : productsBusy ||
            (query.isSuccess && (explanationsQuery.isPending || explanationsQuery.isLoading)) ? (
            <SearchInsightPanelSkeleton />
          ) : query.isSuccess && query.data && explanationsQuery.data ? (
            <SearchInsightPanel
              personalized={query.data.personalized}
              query={q}
              explanations={explanationsQuery.data.search}
            />
          ) : query.isSuccess && query.data && explanationsQuery.isError ? (
            <p className={`rounded-card border border-outline/40 bg-surface/80 px-5 py-4 text-sm ${tw.muted}`}>
              Ranking explanations could not be loaded; results still reflect your filters and sort order.
            </p>
          ) : null}

          {productsBusy ? (
            <>
              <SearchFiltersToolbarSkeleton />
              <CatalogProductGridSkeleton />
            </>
          ) : query.data ? (
            <>
              <CatalogToolbar
                showCategory={false}
                categories={[]}
                activeCategory=""
                activeSort={sort}
                resultsLoading={false}
                total={query.data.total}
                totalFiltered={query.data.total}
                page={query.data.page}
                pageSize={query.data.pageSize}
                activeVertical={vertical}
                freeDeliveryOnly={freeDelivery === "true"}
                facets={query.data.facets}
                onCategoryChange={noopCategory}
                onSortChange={updateSort}
                onVerticalChange={updateVertical}
                onFreeDeliveryToggle={updateFreeDelivery}
              />

              {query.data.items.length === 0 ? (
                <div
                  className="flex flex-1 flex-col items-center gap-10 py-12 sm:gap-12 sm:py-16"
                  aria-live="polite"
                >
                  <div className="relative w-full max-w-[min(100%,22rem)]">
                    <div
                      className="aspect-3/4 w-full overflow-hidden rounded-[2.25rem] shadow-[0_28px_72px_rgba(34,28,23,0.14)] ring-1 ring-ink/8 sm:rotate-[-1.25deg]"
                      style={{ clipPath: "ellipse(92% 96% at 50% 48%)" }}
                    >
                      <img
                        src={SEARCH_NO_RESULTS_IMAGE}
                        alt=""
                        className="h-full w-full object-cover"
                        width={960}
                        height={1280}
                        loading="lazy"
                        decoding="async"
                      />
                    </div>
                    <div
                      className="pointer-events-none absolute -inset-3 -z-10 rounded-[2.5rem] bg-[radial-gradient(ellipse_at_30%_20%,rgba(34,28,23,0.06),transparent_55%)]"
                      aria-hidden
                    />
                  </div>
                  <div className="max-w-md text-center">
                    <h2 className={`${tw.displayH2} text-2xl sm:text-[1.65rem]`}>No surfaces match this query</h2>
                    <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
                      Try a broader keyword, clear department or delivery filters, or browse the full catalog signals
                      still inform ranking when you return.
                    </p>
                    <Link to="/catalog" className={`mt-6 inline-flex ${tw.buttonEditorialBag}`}>
                      Browse catalog
                    </Link>
                  </div>
                </div>
              ) : (
                <ProductGrid
                  products={query.data.items}
                  accent={query.data.personalized ? "Boosted for your signals" : "Generic ranking"}
                />
              )}

              {query.data.items.length > 0 && totalPages > 1 ? (
                <nav
                  className="mt-2 flex flex-wrap items-center justify-center gap-4 border-t border-outline/12 pt-6 sm:pt-7"
                  aria-label="Search results pagination"
                >
                  <button
                    type="button"
                    className={tw.buttonGhost}
                    disabled={pageNum <= 1}
                    onClick={() => setPage(pageNum - 1)}
                  >
                    Previous
                  </button>
                  <span className={`text-sm ${tw.muted}`}>
                    Page {pageNum} of {totalPages}
                  </span>
                  <button
                    type="button"
                    className={tw.buttonGhost}
                    disabled={pageNum >= totalPages}
                    onClick={() => setPage(pageNum + 1)}
                  >
                    Next
                  </button>
                </nav>
              ) : null}
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}

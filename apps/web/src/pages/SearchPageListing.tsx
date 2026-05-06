import { useEffect, useMemo, useRef } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { CatalogToolbar } from "@/features/catalog/components/CatalogToolbar";
import {
  CatalogProductGridSkeleton,
  SearchFiltersToolbarSkeleton,
} from "@/features/catalog/components/CatalogSkeletons";
import { ListingEmptyFiltered } from "@/features/catalog/components/ListingEmptyFiltered";
import { ProductGrid } from "@/features/catalog/components/ProductGrid";
import { Context } from "@/features/events/contexts";
import { useSpecTrack } from "@/features/events/specEvents";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { recommendProductsToProducts } from "@/features/recommendations/mappers";
import { resolveRailCopy } from "@/features/recommendations/railCopy";
import { useFacetStripBusyForScopeChange } from "../features/catalog/hooks/useFacetStripBusyForScopeChange";
import { useSearchFacets } from "@/features/catalog/hooks/useSearchFacets";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

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

/**
 * Search listing shell: insights + toolbar + grid + pagination.
 * Isolated so URL updates from filters/sort/page do not force the editorial header above to re-render.
 */
export function SearchPageListing() {
  const [params, setParams] = useSearchParams();
  const trackSpec = useSpecTrack();
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
    placeholderData: keepPreviousData,
  });

  const facetsQuery = useSearchFacets({ q, vertical, freeDelivery });

  const initialListLoading = Boolean(q) && !query.data && (query.isPending || query.isLoading);
  const { facetFiltersBusy } = useFacetStripBusyForScopeChange(q, facetsQuery);
  const { resultsLoading } = useFacetStripBusyForScopeChange(q, query);
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
    trackSpec("filter_applied", {
      category: q || "search",
      filter_type: "sort",
      filter_value: nextSort,
      surface: "search",
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
    trackSpec("filter_applied", {
      category: q || "search",
      filter_type: "vertical",
      filter_value: nextVertical || "all",
      surface: "search",
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
    trackSpec("filter_applied", {
      category: q || "search",
      filter_type: "free_delivery",
      filter_value: only ? "true" : "false",
      surface: "search",
    });
  };

  const noopCategory = () => {};

  const clearSearchFacetFilters = () => {
    const next = new URLSearchParams(params);
    next.delete("vertical");
    next.delete("freeDelivery");
    next.delete("page");
    setParams(next);
  };

  const hasSearchFacetFilters = Boolean(vertical) || freeDelivery === "true";

  // Spec `search` event — fire once per (q, results_count) pair as soon as
  // results land. Firing here (rather than on form submit) lets us include
  // an accurate `results_count`; the deduper guards React StrictMode and
  // the back/forward cache. Pagination doesn't re-fire because we only
  // fire on the first page.
  const lastTrackedSearchRef = useRef<string | null>(null);
  useEffect(() => {
    if (!q) return;
    if (!query.data) return;
    if (page !== "1") return;
    const stamp = `${q}::${query.data.total}`;
    if (lastTrackedSearchRef.current === stamp) return;
    lastTrackedSearchRef.current = stamp;
    trackSpec("search", {
      query: q,
      results_count: query.data.total,
      page: Number(page) || 1,
      sort: params.get("sort") ?? "relevance",
    });
  }, [q, page, query.data, trackSpec]);

  // Two `/recommend` calls on this page:
  //   - `queryContext` weaves the live query + filters into the context so
  //     the recommender can lean into the user's intent ("more like what
  //     you searched for"). Skipped on empty-result pages — the no-results
  //     fallback below is more useful than a query-shaped rail with nothing
  //     to anchor on.
  //   - `searchContext` is the original generic / no-results "sponsored"
  //     slot. Profile-driven, decoupled from the query so it still shows
  //     reorder / trending picks even when the search itself is sparse.
  const isEmptyResults = Boolean(q) && query.data && query.data.items.length === 0;
  const searchContext = isEmptyResults ? Context.noResults() : Context.search();
  const queryContext = Context.searchResults(q, {
    vertical: vertical || undefined,
    freeDelivery: freeDelivery === "true",
  });
  const recommendationsQuery = useQuery({
    queryKey: ["recommend", searchContext],
    queryFn: () => apiClient.getRecommendation(searchContext),
    enabled: q.length > 0 && Boolean(query.data),
  });
  const queryRecommendationsQuery = useQuery({
    queryKey: ["recommend", queryContext],
    queryFn: () => apiClient.getRecommendation(queryContext),
    enabled: q.length > 0 && Boolean(query.data) && !isEmptyResults,
  });

  return (
    <div className={`${tw.stackLg} flex flex-1 flex-col`}>
      {query.isError ? (
        <p className="text-sm text-red-800/90" role="alert">
          Could not load search results. Check your connection and try again.
        </p>
      ) : null}

      {initialListLoading ? (
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
            facetFiltersBusy={facetFiltersBusy}
            resultsLoading={resultsLoading}
            total={query.data.total}
            totalFiltered={query.data.total}
            page={query.data.page}
            pageSize={query.data.pageSize}
            activeVertical={vertical}
            freeDeliveryOnly={freeDelivery === "true"}
            facets={facetsQuery.data}
            onCategoryChange={noopCategory}
            onSortChange={updateSort}
            onVerticalChange={updateVertical}
            onFreeDeliveryToggle={updateFreeDelivery}
          />

          {query.data.items.length === 0 ? (
            <ListingEmptyFiltered
              headline="No surfaces match this query"
              body="Try a broader keyword, clear department or delivery filters, or browse the full catalog—signals still inform ranking when you return."
              hasFacetFilters={hasSearchFacetFilters}
              onClearFacetFilters={clearSearchFacetFilters}
            />
          ) : (
            <div
              aria-busy={query.isPlaceholderData && query.isFetching}
              className={
                query.isPlaceholderData && query.isFetching
                  ? "opacity-[0.72] transition-opacity duration-300 motion-reduce:transition-none"
                  : undefined
              }
            >
              <ProductGrid
                products={query.data.items}
                accent={query.data.personalized ? "Boosted for your signals" : undefined}
              />
            </div>
          )}

          {query.data.items.length > 0 && totalPages > 1 ? (
            <nav
              className="mt-4 flex flex-wrap items-center justify-center gap-4 border-t border-outline/15 pt-6 sm:pt-7"
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

          {queryRecommendationsQuery.data && queryRecommendationsQuery.data.products.length > 0
            ? (() => {
                const rail = resolveRailCopy(queryRecommendationsQuery.data, {
                  eyebrow: "Tuned to your search",
                  headline: q ? `More picks shaped by “${q}”` : "More picks shaped by your search",
                  subtitle: "Ranked against your query and the filters you've applied.",
                  modeLabel: "Query-aware picks",
                });
                return (
                  <RecommendationRail
                    products={recommendProductsToProducts(queryRecommendationsQuery.data.products)}
                    sourceContext={queryContext}
                    title={rail.headline}
                    subtitle={rail.eyebrow}
                    reason={rail.subtitle}
                    personalized={Boolean(queryRecommendationsQuery.data.personalization_reason)}
                    modeLabel={rail.mode_label}
                    presentation="default"
                  />
                );
              })()
            : null}

          {recommendationsQuery.data && recommendationsQuery.data.products.length > 0
            ? (() => {
                const rail = resolveRailCopy(recommendationsQuery.data, {
                  eyebrow: isEmptyResults ? "No results" : "Sponsored slot",
                  headline: isEmptyResults ? "Try one of these instead" : "You might also like",
                  subtitle: isEmptyResults
                    ? "A few staples we'd recommend in their place."
                    : "Curated picks based on your search.",
                  modeLabel: "Curated picks",
                });
                return (
                  <RecommendationRail
                    products={recommendProductsToProducts(recommendationsQuery.data.products)}
                    sourceContext={searchContext}
                    title={rail.headline}
                    subtitle={rail.eyebrow}
                    reason={rail.subtitle}
                    personalized={Boolean(recommendationsQuery.data.personalization_reason)}
                    modeLabel={rail.mode_label}
                    presentation="default"
                  />
                );
              })()
            : null}
        </>
      ) : null}
    </div>
  );
}

import { useMemo } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { CatalogToolbar } from "@/features/catalog/components/CatalogToolbar";
import {
  CatalogProductGridSkeleton,
  SearchFiltersToolbarSkeleton,
} from "@/features/catalog/components/CatalogSkeletons";
import { ListingEmptyFiltered } from "@/features/catalog/components/ListingEmptyFiltered";
import { ProductGrid } from "@/features/catalog/components/ProductGrid";
import { useDebugEventStore } from "@/features/events/debug/store";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import { SearchInsightPanel, SearchInsightPanelSkeleton } from "@/features/search/components/SearchInsightPanel";
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
  const track = useTrackEvent();
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

  const explanationsQuery = useQuery({
    queryKey: ["explanations", q],
    queryFn: apiClient.getExplanations,
    enabled: q.length > 0,
  });

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

  const clearSearchFacetFilters = () => {
    const next = new URLSearchParams(params);
    next.delete("vertical");
    next.delete("freeDelivery");
    next.delete("page");
    setParams(next);
  };

  const hasSearchFacetFilters = Boolean(vertical) || freeDelivery === "true";
  const recentContextChange = useDebugEventStore((state) =>
    state.events.find((event) => event.event_type === "consent_updated" || event.event_type === "profile_updated"),
  );
  const rankingContextChange = recentContextChange
    ? {
        source: recentContextChange.event_type === "consent_updated" ? ("consent" as const) : ("profile" as const),
        at: recentContextChange.created_at,
      }
    : null;

  return (
    <div className={`${tw.stackLg} flex flex-1 flex-col`}>
      {query.isError ? (
        <p className="text-sm text-red-800/90" role="alert">
          Could not load search results. Check your connection and try again.
        </p>
      ) : null}

      {query.data ? (
        <div className="flex flex-wrap items-center gap-2" aria-live="polite">
          <span className={query.data.personalized ? tw.chipSuccess : tw.chipWarning}>
            {query.data.personalized ? "Personalized ranking active" : "Generic ranking mode"}
          </span>
          <span className={tw.chipInfo}>Query: {q || "None"}</span>
        </div>
      ) : null}

      {query.isError ? null : initialListLoading ||
        (query.isSuccess && (explanationsQuery.isPending || explanationsQuery.isLoading)) ? (
        <SearchInsightPanelSkeleton />
      ) : query.isSuccess && query.data && explanationsQuery.data ? (
        <SearchInsightPanel
          personalized={query.data.personalized}
          query={q}
          explanations={explanationsQuery.data.search}
          rankingContextChange={rankingContextChange}
        />
      ) : query.isSuccess && query.data && explanationsQuery.isError ? (
        <p className={`rounded-card border border-outline/40 bg-surface/80 px-5 py-4 text-sm ${tw.muted}`}>
          Ranking explanations could not be loaded; results still reflect your filters and sort order.
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
                accent={query.data.personalized ? "Boosted for your signals" : "Generic ranking"}
              />
            </div>
          )}

          {query.data.items.length > 0 && totalPages > 1 ? (
            <nav
              className={`${tw.labPanel} mt-2 flex flex-wrap items-center justify-center gap-4 border-t border-outline/12 pt-6 sm:pt-7`}
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
  );
}

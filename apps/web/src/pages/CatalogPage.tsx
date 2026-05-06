import { memo, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { CatalogToolbar } from "@/features/catalog/components/CatalogToolbar";
import {
  CatalogProductGridSkeleton,
  CatalogToolbarSkeleton,
} from "@/features/catalog/components/CatalogSkeletons";
import { ListingEmptyFiltered } from "@/features/catalog/components/ListingEmptyFiltered";
import { ProductGrid } from "@/features/catalog/components/ProductGrid";
import { Context } from "@/features/events/contexts";
import { useSpecTrack } from "@/features/events/specEvents";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { recommendProductsToProducts } from "@/features/recommendations/mappers";
import { useCatalogFacets } from "@/features/catalog/hooks/useCatalogFacets";
import { useFacetStripBusyForScopeChange } from "../features/catalog/hooks/useFacetStripBusyForScopeChange";
import { useProductSearch } from "@/features/catalog/hooks/useProductSearch";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

/** Static hero — filter/sort URL updates do not re-render this subtree. */
const CatalogPageIntro = memo(function CatalogPageIntro() {
  return (
    <header className="max-w-3xl">
      <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Catalog</p>
      <h1 className={`${tw.storyTitle} max-w-[18ch]`}>Browse editorial product surfaces the way a real shopper would.</h1>
      <p className={`mt-3 max-w-2xl text-sm leading-relaxed ${tw.muted}`}>
        Filters update quickly in place, while category changes can refresh the facet structure.
      </p>
    </header>
  );
});

export function CatalogPage() {
  const [params, setParams] = useSearchParams();
  const trackSpec = useSpecTrack();
  const category = params.get("category") ?? "";
  const sort = params.get("sort") ?? "featured";
  const page = params.get("page") ?? "1";
  const vertical = params.get("vertical") ?? "";
  const freeDelivery = params.get("freeDelivery") === "true" ? "true" : "";
  const query = useProductSearch({ category, sort, page, vertical, freeDelivery });
  const facetsQuery = useCatalogFacets({ category, vertical, freeDelivery });
  const categoriesQuery = useQuery({
    queryKey: ["categories"],
    queryFn: apiClient.getCategories,
  });

  // Spec `category_view` — fire once per category landing/change, not per
  // sort/page change. Tracks the canonical category slug ("all" for the
  // unfiltered catalog landing) so the recommender can attribute browse
  // intent without conflating filter clicks.
  const lastCategoryRef = useRef<string | null>(null);
  useEffect(() => {
    const slug = category || "all";
    if (lastCategoryRef.current === slug) return;
    lastCategoryRef.current = slug;
    trackSpec("category_view", { category: slug });
  }, [category, trackSpec]);

  // Spec context: only meaningful when the user has scoped to a category.
  // The unfiltered landing has no good slug for the recommender — skip the
  // call rather than spam `category:all` (which would balloon Redis keys).
  const categoryContext = category ? Context.category(category) : "";
  const recommendationsQuery = useQuery({
    queryKey: ["recommend", categoryContext],
    queryFn: () => apiClient.getRecommendation(categoryContext),
    enabled: categoryContext.length > 0,
  });

  const updateCategory = (nextCategory: string) => {
    const next = new URLSearchParams(params);
    if (nextCategory) {
      next.set("category", nextCategory);
    } else {
      next.delete("category");
    }
    next.delete("page");
    setParams(next);
    // `category_view` fires from the effect above when `category` changes;
    // the URL update here triggers the effect on next render.
  };

  const updateSort = (nextSort: string) => {
    const next = new URLSearchParams(params);
    next.set("sort", nextSort);
    next.delete("page");
    setParams(next);
    trackSpec("filter_applied", {
      category: category || "all",
      filter_type: "sort",
      filter_value: nextSort,
      surface: "catalog",
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
      category: category || "all",
      filter_type: "vertical",
      filter_value: nextVertical || "all",
      surface: "catalog",
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
      category: category || "all",
      filter_type: "free_delivery",
      filter_value: only ? "true" : "false",
      surface: "catalog",
    });
  };

  const setPage = (nextPage: number) => {
    const next = new URLSearchParams(params);
    if (nextPage <= 1) {
      next.delete("page");
    } else {
      next.set("page", String(nextPage));
    }
    setParams(next);
  };

  const clearFacetFilters = () => {
    const next = new URLSearchParams(params);
    next.delete("vertical");
    next.delete("freeDelivery");
    next.delete("page");
    setParams(next);
  };

  const clearCategoryScope = () => {
    const next = new URLSearchParams(params);
    next.delete("category");
    next.delete("page");
    setParams(next);
  };

  const hasFacetFilters = Boolean(vertical) || freeDelivery === "true";

  const pageNum = Math.max(1, Number(page || "1"));
  const pageSize = query.data?.pageSize ?? 12;
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const categoriesReady = Boolean(categoriesQuery.data);
  const categoriesBusy = categoriesQuery.isPending || categoriesQuery.isLoading;
  /**
   * Facet strip skeleton tracks the **facets** query (separate cache, no `sort`/`page` in key) — so sort/page never trigger it.
   * “Loading results…” summary tracks the **products** query because it summarizes the list count.
   */
  const { facetFiltersBusy } = useFacetStripBusyForScopeChange(category, facetsQuery);
  const { resultsLoading } = useFacetStripBusyForScopeChange(category, query);

  return (
    <div className={`${tw.stackLg} pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
      <CatalogPageIntro />

      {query.isError ? (
        <p className="text-sm text-red-800/90" role="alert">
          Could not load products. Check your connection and try again.
        </p>
      ) : null}

      {!categoriesReady && categoriesBusy ? (
        <CatalogToolbarSkeleton />
      ) : categoriesQuery.data ? (
        <CatalogToolbar
          categories={categoriesQuery.data}
          activeCategory={category}
          activeSort={sort}
          facetFiltersBusy={facetFiltersBusy}
          resultsLoading={resultsLoading}
          total={query.data?.total ?? 0}
          totalFiltered={query.data?.total}
          page={query.data?.page ?? 1}
          pageSize={query.data?.pageSize ?? pageSize}
          activeVertical={vertical}
          freeDeliveryOnly={freeDelivery === "true"}
          facets={facetsQuery.data}
          onCategoryChange={updateCategory}
          onSortChange={updateSort}
          onVerticalChange={updateVertical}
          onFreeDeliveryToggle={updateFreeDelivery}
        />
      ) : null}

      {!query.data ? (
        <CatalogProductGridSkeleton />
      ) : query.data.items.length === 0 ? (
        <ListingEmptyFiltered
          hasFacetFilters={hasFacetFilters}
          hasCategoryScope={Boolean(category)}
          onClearFacetFilters={clearFacetFilters}
          onClearCategoryScope={clearCategoryScope}
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
          <ProductGrid products={query.data.items} />
        </div>
      )}

      {query.data && totalPages > 1 ? (
        <nav
          className="mt-4 flex flex-wrap items-center justify-center gap-4 border-t border-outline/15 pt-6 sm:pt-7"
          aria-label="Catalog pagination"
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

      {recommendationsQuery.data && categoryContext && recommendationsQuery.data.products.length > 0 ? (
        <RecommendationRail
          products={recommendProductsToProducts(recommendationsQuery.data.products)}
          sourceContext={categoryContext}
          title="Worth a closer look in this category"
          subtitle="Recommended"
          reason={recommendationsQuery.data.personalization_reason ?? undefined}
          personalized={Boolean(recommendationsQuery.data.personalization_reason)}
          presentation="default"
        />
      ) : null}
    </div>
  );
}

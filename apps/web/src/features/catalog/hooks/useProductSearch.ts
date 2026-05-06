import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useDeferredValue } from "react";

import { apiClient } from "@/shared/api/client";

type UseProductSearchArgs = {
  search?: string;
  category?: string;
  sort?: string;
  page?: string;
  vertical?: string;
  freeDelivery?: string;
};

export function useProductSearch({
  search,
  category,
  sort,
  page = "1",
  vertical,
  freeDelivery,
}: UseProductSearchArgs) {
  const deferredSearch = useDeferredValue(search ?? "");
  const query = new URLSearchParams();

  if (deferredSearch) {
    query.set("q", deferredSearch);
  }
  if (category) {
    query.set("category", category);
  }
  if (sort) {
    query.set("sort", sort);
  }
  query.set("page", page || "1");
  query.set("pageSize", "12");
  if (vertical) {
    query.set("vertical", vertical);
  }
  if (freeDelivery === "true") {
    query.set("freeDelivery", "true");
  }

  return useQuery({
    queryKey: ["products", deferredSearch, category, sort, page, vertical, freeDelivery],
    queryFn: () => apiClient.getProducts(`?${query.toString()}`),
    /** Keeps grid stable while sort/page/filters change; facets use `useCatalogFacets` / `useSearchFacets` (separate cache). */
    placeholderData: keepPreviousData,
  });
}

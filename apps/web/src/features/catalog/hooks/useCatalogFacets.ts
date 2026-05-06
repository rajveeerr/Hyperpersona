import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";

/**
 * Facet counts / pills for browse — keyed without sort or page so paging/sorting does not refetch facets.
 * Separate from the product grid query (same filters: category, vertical, free delivery).
 */
export function useCatalogFacets(args: {
  category: string;
  vertical: string;
  freeDelivery: string;
}) {
  const params = new URLSearchParams();
  if (args.category) {
    params.set("category", args.category);
  }
  if (args.vertical) {
    params.set("vertical", args.vertical);
  }
  if (args.freeDelivery === "true") {
    params.set("freeDelivery", "true");
  }
  const qs = params.toString() ? `?${params.toString()}` : "";

  return useQuery({
    queryKey: ["catalog-facets", args.category, args.vertical, args.freeDelivery],
    queryFn: () => apiClient.getCatalogFacets(qs),
    placeholderData: keepPreviousData,
  });
}

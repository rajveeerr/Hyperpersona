import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";

/**
 * Search facet strip — same as {@link useCatalogFacets} but scoped by `q` (no page/sort in the key).
 */
export function useSearchFacets(args: { q: string; vertical: string; freeDelivery: string }) {
  const params = new URLSearchParams();
  params.set("q", args.q);
  if (args.vertical) {
    params.set("vertical", args.vertical);
  }
  if (args.freeDelivery === "true") {
    params.set("freeDelivery", "true");
  }

  return useQuery({
    queryKey: ["search-facets", args.q, args.vertical, args.freeDelivery],
    queryFn: () => apiClient.getCatalogFacets(`?${params.toString()}`),
    enabled: args.q.length > 0,
    placeholderData: keepPreviousData,
  });
}

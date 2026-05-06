import { useRef } from "react";

import type { UseQueryResult } from "@tanstack/react-query";

type QuerySlice<TData> = Pick<UseQueryResult<TData, Error>, "data" | "isPending" | "isPlaceholderData">;

/**
 * Skeleton policy for the facet strip / “Loading results…” summary.
 *
 * **Single rule:** the skeleton is allowed to render only when the **browse/search scope** (`category` / `q`) changes,
 * never on sort, page, vertical, or freeDelivery clicks. Counts inside an unchanged pill set update silently via
 * `keepPreviousData` on the underlying query.
 *
 * Implementation notes:
 * - Tracks the **scope of the last non-placeholder response** in a ref written **during render** (not in `useEffect`,
 *   since effects run after paint and would let the first settled frame still see the stale ref).
 * - The "is the strip busy?" flag is derived purely from `lastSettledScopeRef.current vs. scopeKey`, so it does not
 *   depend on React Query internals like `isFetching` / `isPlaceholderData` that can transiently flip during
 *   sort / page / pill refetches and accidentally re-trigger the skeleton.
 * - First-ever render (no prior settled scope) shows the skeleton only while the query is still in `isPending`.
 */
export function useFacetStripBusyForScopeChange<TData>(
  scopeKey: string,
  query: QuerySlice<TData>,
): { facetFiltersBusy: boolean; resultsLoading: boolean } {
  const lastSettledScopeRef = useRef<string | null>(null);

  if (query.data != null && !query.isPlaceholderData) {
    lastSettledScopeRef.current = scopeKey;
  }

  const hasEverSettled = lastSettledScopeRef.current !== null;
  const scopeChangedSinceLastResponse = hasEverSettled && lastSettledScopeRef.current !== scopeKey;
  const coldStart = !hasEverSettled && !query.data && query.isPending;

  const busy = coldStart || scopeChangedSinceLastResponse;
  return { facetFiltersBusy: busy, resultsLoading: busy };
}

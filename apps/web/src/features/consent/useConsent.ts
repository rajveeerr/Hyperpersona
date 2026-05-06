import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/useAuth";
import { apiClient } from "@/shared/api/client";
import { ApiError, type ConsentRecord } from "@/shared/api/contracts";

export type ConsentUpdate = {
  scopes: string[];
  data_retention_days?: number;
};

/**
 * Identity-scoped consent loader. Mirrors `GET /consent` semantics:
 *   - 404 → no record yet (`status === "missing"`); UI should let the user
 *     create one with default scopes.
 *   - 200 → record present (`status === "present"`).
 *   - 401 → handled globally by `AuthExpiredListener` via the `apiClient`.
 *
 * Skips the request entirely when there is no session, so unauthenticated
 * surfaces (e.g. the floating consent banner on the home page before login)
 * don't churn the network or the auth-expired listener.
 */
export function useConsentQuery() {
  const { isAuthenticated, customerId } = useAuth();
  const query = useQuery<ConsentRecord, ApiError>({
    queryKey: ["consent", customerId],
    queryFn: apiClient.getConsent,
    enabled: isAuthenticated,
    retry: (failureCount, error) => {
      // 404 is a normal state, not a fetch failure — never retry it.
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });

  const isMissing = query.error instanceof ApiError && query.error.status === 404;

  return {
    ...query,
    record: query.data ?? null,
    /**
     * True when the server explicitly says no record exists yet. Distinguishes
     * the "first-time user" empty state from a transient fetch error.
     */
    isMissing,
    /** True for any error that isn't the legitimate 404 missing-record state. */
    isFatalError: query.isError && !isMissing,
  };
}

export function useConsentMutation() {
  const queryClient = useQueryClient();
  const { customerId } = useAuth();

  return useMutation({
    mutationFn: ({ scopes, data_retention_days }: ConsentUpdate) =>
      apiClient.updateConsent(scopes, data_retention_days),
    onSuccess: (next) => {
      // Cache under the active identity. If the user later switches accounts
      // the auth flow already calls `queryClient.clear()` so stale data
      // can't leak across identities.
      queryClient.setQueryData(["consent", customerId], next);
    },
  });
}

/**
 * Server-state orders hook — paginated `/me/orders` read.
 * Mirrors the wishlist/cart pattern: React Query is the source of truth.
 */

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/useAuth";
import { apiClient } from "@/shared/api/client";
import {
  ApiError,
  type OrderListResponse,
} from "@/shared/api/contracts";

function ordersKey(customerId: string | null, page: number, pageSize: number): readonly unknown[] {
  return ["orders", customerId, page, pageSize];
}

type UseOrdersQueryArgs = {
  page?: number;
  pageSize?: number;
};

export function useOrdersQuery({ page = 1, pageSize = 20 }: UseOrdersQueryArgs = {}) {
  const { customerId, isAuthenticated } = useAuth();
  return useQuery<OrderListResponse, ApiError>({
    queryKey: ordersKey(customerId, page, pageSize),
    queryFn: () => apiClient.getOrders(`?page=${page}&pageSize=${pageSize}`),
    enabled: isAuthenticated,
    staleTime: 30 * 1000,
  });
}

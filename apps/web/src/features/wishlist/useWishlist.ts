/**
 * Server-state wishlist hooks — replaces the previous Zustand+localStorage store.
 * Same shape as `useCart`: React Query is the source of truth, mutations
 * apply optimistic updates that the server response reconciles on settle.
 */

import { useCallback } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import { useAuth } from "@/features/auth/useAuth";
import { apiClient } from "@/shared/api/client";
import {
  ApiError,
  type WishlistLine,
  type WishlistResponse,
} from "@/shared/api/contracts";

const EMPTY_WISHLIST: WishlistResponse = { items: [] };

function wishlistKey(customerId: string | null): readonly unknown[] {
  return ["wishlist", customerId];
}

export function useWishlistQuery() {
  const { customerId, isAuthenticated } = useAuth();
  return useQuery<WishlistResponse, ApiError>({
    queryKey: wishlistKey(customerId),
    queryFn: apiClient.getWishlist,
    enabled: isAuthenticated,
    staleTime: 30 * 1000,
  });
}

/** Convenience selector for the header badge. */
export function useWishlistCount(): number {
  const { data } = useWishlistQuery();
  return data?.items.length ?? 0;
}

/** Membership check by product id. */
export function useIsInWishlist(productId: string): boolean {
  const { data } = useWishlistQuery();
  if (!productId) return false;
  return Boolean(data?.items.some((line) => line.productId === productId));
}

type MutationOpts<TVars> = Omit<
  UseMutationOptions<WishlistResponse, ApiError, TVars>,
  "mutationFn" | "onMutate" | "onError" | "onSettled"
>;

function applyOptimistic(
  queryClient: ReturnType<typeof useQueryClient>,
  customerId: string | null,
  updater: (prev: WishlistResponse) => WishlistResponse,
) {
  const key = wishlistKey(customerId);
  const prev = queryClient.getQueryData<WishlistResponse>(key) ?? EMPTY_WISHLIST;
  queryClient.setQueryData<WishlistResponse>(key, updater(prev));
  return prev;
}

/**
 * Add a product to the wishlist. Optimistic insert uses a synthetic
 * `WishlistLine` with placeholder metadata; the server response on settle
 * replaces it with the real product fields.
 */
export function useAddToWishlist(opts: MutationOpts<{ productId: string; productSnapshot?: Partial<WishlistLine> }> = {}) {
  const queryClient = useQueryClient();
  const { customerId } = useAuth();
  return useMutation<
    WishlistResponse,
    ApiError,
    { productId: string; productSnapshot?: Partial<WishlistLine> },
    { prev: WishlistResponse }
  >({
    mutationFn: ({ productId }) => apiClient.addWishlistItem({ productId }),
    onMutate: async ({ productId, productSnapshot }) => {
      const key = wishlistKey(customerId);
      await queryClient.cancelQueries({ queryKey: key });
      const prev = applyOptimistic(queryClient, customerId, (current) => {
        if (current.items.some((line) => line.productId === productId)) return current;
        const optimistic: WishlistLine = {
          productId,
          slug: productSnapshot?.slug ?? "",
          name: productSnapshot?.name ?? "Saving…",
          image: productSnapshot?.image ?? "",
          unitPrice: productSnapshot?.unitPrice ?? 0,
          addedAt: new Date().toISOString(),
        };
        return { items: [...current.items, optimistic] };
      });
      return { prev };
    },
    onError: (_err, _vars, context) => {
      if (context) queryClient.setQueryData(wishlistKey(customerId), context.prev);
    },
    onSettled: (data) => {
      if (data) queryClient.setQueryData(wishlistKey(customerId), data);
      else queryClient.invalidateQueries({ queryKey: wishlistKey(customerId) });
    },
    ...opts,
  });
}

export function useRemoveFromWishlist(opts: MutationOpts<string> = {}) {
  const queryClient = useQueryClient();
  const { customerId } = useAuth();
  return useMutation<WishlistResponse, ApiError, string, { prev: WishlistResponse }>({
    mutationFn: (productId) => apiClient.deleteWishlistItem(productId),
    onMutate: async (productId) => {
      const key = wishlistKey(customerId);
      await queryClient.cancelQueries({ queryKey: key });
      const prev = applyOptimistic(queryClient, customerId, (current) => ({
        items: current.items.filter((line) => line.productId !== productId),
      }));
      return { prev };
    },
    onError: (_err, _id, context) => {
      if (context) queryClient.setQueryData(wishlistKey(customerId), context.prev);
    },
    onSettled: (data) => {
      if (data) queryClient.setQueryData(wishlistKey(customerId), data);
      else queryClient.invalidateQueries({ queryKey: wishlistKey(customerId) });
    },
    ...opts,
  });
}

export function useInvalidateWishlist() {
  const queryClient = useQueryClient();
  const { customerId } = useAuth();
  return useCallback(() => {
    queryClient.invalidateQueries({ queryKey: wishlistKey(customerId) });
  }, [queryClient, customerId]);
}

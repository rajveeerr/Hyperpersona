/**
 * Server-state cart hooks — replaces the previous Zustand+localStorage store.
 *
 * Source of truth is the BE (`/me/cart`). React Query holds the per-session
 * cache; on logout the entire cache is cleared by the auth flow, so cross-
 * identity bleed is impossible.
 *
 * Mutations apply optimistic updates so the UI feels instant. The
 * server response always wins on settle, so any pricing/qty drift the BE
 * applies (e.g. quantity caps, out-of-stock) is reconciled in the next render.
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
  type AddCartItemBody,
  type CartResponse,
  type PatchCartItemBody,
} from "@/shared/api/contracts";

const EMPTY_CART: CartResponse = { items: [], itemCount: 0, subtotal: 0 };

function cartKey(customerId: string | null): readonly unknown[] {
  return ["cart", customerId];
}

/**
 * Read the current cart. Disabled when unauthenticated — the BE 401s on
 * `/me/cart` without a JWT, and we already redirect to /login in that case.
 */
export function useCartQuery() {
  const { customerId, isAuthenticated } = useAuth();
  return useQuery<CartResponse, ApiError>({
    queryKey: cartKey(customerId),
    queryFn: apiClient.getCart,
    enabled: isAuthenticated,
    staleTime: 30 * 1000,
  });
}

/** Convenience selector — total quantity across all lines, used for the header badge. */
export function useCartCount(): number {
  const { data } = useCartQuery();
  return data?.itemCount ?? 0;
}

/** True if a given productId is in the cart. */
export function useIsInCart(productId: string): boolean {
  const { data } = useCartQuery();
  if (!productId) return false;
  return Boolean(data?.items.some((line) => line.productId === productId));
}

type MutationOpts<TVars> = Omit<
  UseMutationOptions<CartResponse, ApiError, TVars>,
  "mutationFn" | "onMutate" | "onError" | "onSettled"
>;

function applyOptimistic(
  queryClient: ReturnType<typeof useQueryClient>,
  customerId: string | null,
  updater: (prev: CartResponse) => CartResponse,
) {
  const key = cartKey(customerId);
  const prev = queryClient.getQueryData<CartResponse>(key) ?? EMPTY_CART;
  queryClient.setQueryData<CartResponse>(key, updater(prev));
  return prev;
}

/** Add an item to the cart. Optimistic update bumps quantity if the line exists. */
export function useAddToCart(opts: MutationOpts<AddCartItemBody> = {}) {
  const queryClient = useQueryClient();
  const { customerId } = useAuth();
  return useMutation<CartResponse, ApiError, AddCartItemBody, { prev: CartResponse }>({
    mutationFn: (body) => apiClient.addCartItem(body),
    onMutate: async (body) => {
      const key = cartKey(customerId);
      await queryClient.cancelQueries({ queryKey: key });
      const prev = applyOptimistic(queryClient, customerId, (current) => {
        const idx = current.items.findIndex((line) => line.productId === body.productId);
        const qty = body.quantity ?? 1;
        const items = [...current.items];
        if (idx >= 0) {
          items[idx] = { ...items[idx], quantity: items[idx].quantity + qty };
        } else {
          // Skeleton line; the server response on settle replaces this with
          // the real product metadata (slug, name, image, unitPrice).
          items.push({
            productId: body.productId,
            slug: "",
            name: "Adding…",
            image: "",
            unitPrice: 0,
            quantity: qty,
            selectedOptions: body.selectedOptions ?? null,
            addedAt: new Date().toISOString(),
          });
        }
        const itemCount = items.reduce((sum, line) => sum + line.quantity, 0);
        const subtotal = items.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0);
        return { ...current, items, itemCount, subtotal };
      });
      return { prev };
    },
    onError: (_err, _body, context) => {
      if (context) queryClient.setQueryData(cartKey(customerId), context.prev);
    },
    onSettled: (data) => {
      if (data) queryClient.setQueryData(cartKey(customerId), data);
      else queryClient.invalidateQueries({ queryKey: cartKey(customerId) });
    },
    ...opts,
  });
}

/** Update quantity / selectedOptions on an existing line. */
export function useUpdateCartItem(opts: MutationOpts<{ productId: string; body: PatchCartItemBody }> = {}) {
  const queryClient = useQueryClient();
  const { customerId } = useAuth();
  return useMutation<
    CartResponse,
    ApiError,
    { productId: string; body: PatchCartItemBody },
    { prev: CartResponse }
  >({
    mutationFn: ({ productId, body }) => apiClient.patchCartItem(productId, body),
    onMutate: async ({ productId, body }) => {
      const key = cartKey(customerId);
      await queryClient.cancelQueries({ queryKey: key });
      const prev = applyOptimistic(queryClient, customerId, (current) => {
        const items = current.items.map((line) =>
          line.productId === productId
            ? {
                ...line,
                quantity: body.quantity ?? line.quantity,
                selectedOptions: body.selectedOptions ?? line.selectedOptions,
              }
            : line,
        );
        const itemCount = items.reduce((sum, line) => sum + line.quantity, 0);
        const subtotal = items.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0);
        return { ...current, items, itemCount, subtotal };
      });
      return { prev };
    },
    onError: (_err, _vars, context) => {
      if (context) queryClient.setQueryData(cartKey(customerId), context.prev);
    },
    onSettled: (data) => {
      if (data) queryClient.setQueryData(cartKey(customerId), data);
      else queryClient.invalidateQueries({ queryKey: cartKey(customerId) });
    },
    ...opts,
  });
}

/** Remove a line from the cart. */
export function useRemoveFromCart(opts: MutationOpts<string> = {}) {
  const queryClient = useQueryClient();
  const { customerId } = useAuth();
  return useMutation<CartResponse, ApiError, string, { prev: CartResponse }>({
    mutationFn: (productId) => apiClient.deleteCartItem(productId),
    onMutate: async (productId) => {
      const key = cartKey(customerId);
      await queryClient.cancelQueries({ queryKey: key });
      const prev = applyOptimistic(queryClient, customerId, (current) => {
        const items = current.items.filter((line) => line.productId !== productId);
        const itemCount = items.reduce((sum, line) => sum + line.quantity, 0);
        const subtotal = items.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0);
        return { ...current, items, itemCount, subtotal };
      });
      return { prev };
    },
    onError: (_err, _id, context) => {
      if (context) queryClient.setQueryData(cartKey(customerId), context.prev);
    },
    onSettled: (data) => {
      if (data) queryClient.setQueryData(cartKey(customerId), data);
      else queryClient.invalidateQueries({ queryKey: cartKey(customerId) });
    },
    ...opts,
  });
}

/**
 * Used by the checkout flow + delete-account cleanup. Forces a refetch on
 * next mount, which is sufficient since the server is the source of truth.
 */
export function useInvalidateCart() {
  const queryClient = useQueryClient();
  const { customerId } = useAuth();
  return useCallback(() => {
    queryClient.invalidateQueries({ queryKey: cartKey(customerId) });
  }, [queryClient, customerId]);
}

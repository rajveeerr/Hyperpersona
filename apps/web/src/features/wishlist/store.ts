import { persist } from "zustand/middleware";
import { create } from "zustand/react";

import type { Product } from "@/shared/api/contracts";

/**
 * Wishlist is local-only (Zustand + localStorage), mirroring the cart store.
 * It keeps full `Product` snapshots rather than bare IDs so the wishlist page
 * can render without a fetch — which matters now that the FE no longer
 * carries a static product fixture (we removed MSW mocks). Snapshots may go
 * stale if a product is repriced or delisted, which is acceptable for this
 * demo; rendering against the real catalog response on every visit would
 * cost a roundtrip per saved item.
 */
type WishlistStore = {
  items: Product[];
  /** Add or remove based on whether the product is already saved. */
  toggle: (product: Product) => void;
  /** Membership check by product id (the only thing call sites have on tile clicks). */
  has: (productId: string) => boolean;
  remove: (productId: string) => void;
  clear: () => void;
};

export const useWishlistStore = create<WishlistStore>()(
  persist(
    (set, get) => ({
      items: [],
      toggle: (product) =>
        set((state) => {
          const exists = state.items.some((p) => p.id === product.id);
          if (exists) {
            return { items: state.items.filter((p) => p.id !== product.id) };
          }
          return { items: [...state.items, product] };
        }),
      has: (productId) => get().items.some((p) => p.id === productId),
      remove: (productId) =>
        set((state) => ({ items: state.items.filter((p) => p.id !== productId) })),
      clear: () => set({ items: [] }),
    }),
    { name: "hyperpersona-wishlist" },
  ),
);

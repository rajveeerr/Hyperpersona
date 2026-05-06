import { persist } from "zustand/middleware";
import { create } from "zustand/react";

import type { Product } from "@/shared/api/contracts";

export type CartItem = {
  product: Product;
  quantity: number;
};

type CartStore = {
  items: CartItem[];
  addItem: (product: Product) => void;
  removeItem: (productId: string) => void;
  updateQuantity: (productId: string, quantity: number) => void;
  clear: () => void;
};

export const useCartStore = create<CartStore>()(
  persist(
    (set) => ({
      items: [],
      addItem: (product) =>
        set((state) => {
          const existing = state.items.find((item) => item.product.id === product.id);
          if (!existing) {
            return { items: [...state.items, { product, quantity: 1 }] };
          }

          return {
            items: state.items.map((item) =>
              item.product.id === product.id
                ? { ...item, quantity: item.quantity + 1 }
                : item,
            ),
          };
        }),
      removeItem: (productId) =>
        set((state) => ({
          items: state.items.filter((item) => item.product.id !== productId),
        })),
      updateQuantity: (productId, quantity) =>
        set((state) => ({
          items: state.items.map((item) =>
            item.product.id === productId
              ? { ...item, quantity: Math.max(1, quantity) }
              : item,
          ),
        })),
      clear: () => set({ items: [] }),
    }),
    { name: "hyperpersona-cart" },
  ),
);

export function getCartSubtotal(items: CartItem[]) {
  return items.reduce((sum, item) => sum + item.product.price * item.quantity, 0);
}

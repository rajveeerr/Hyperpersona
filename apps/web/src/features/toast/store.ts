import { create } from "zustand";

export type ToastItem = {
  id: string;
  message: string;
};

type ToastState = {
  items: ToastItem[];
  push: (message: string) => void;
  dismiss: (id: string) => void;
};

let seq = 0;

const TOAST_MS = 4200;

export const useToastStore = create<ToastState>((set, get) => ({
  items: [],
  push: (message) => {
    const id = `${Date.now()}-${++seq}`;
    set((s) => ({ items: [...s.items, { id, message }] }));
    window.setTimeout(() => {
      get().dismiss(id);
    }, TOAST_MS);
  },
  dismiss: (id) =>
    set((s) => ({
      items: s.items.filter((t) => t.id !== id),
    })),
}));

export function pushToast(message: string) {
  useToastStore.getState().push(message);
}

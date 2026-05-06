import { useEffect, useState } from "react";

import { useCartStore } from "@/features/cart/store";

type CartStoreWithPersist = typeof useCartStore & {
  persist: {
    hasHydrated: () => boolean;
    onFinishHydration: (fn: () => void) => () => void;
  };
};

const store = useCartStore as CartStoreWithPersist;

/** `false` until persisted cart lines have rehydrated from storage. */
export function useCartHydrated(): boolean {
  const [hydrated, setHydrated] = useState(() => store.persist.hasHydrated());

  useEffect(() => {
    if (store.persist.hasHydrated()) {
      setHydrated(true);
      return;
    }
    return store.persist.onFinishHydration(() => {
      setHydrated(true);
    });
  }, []);

  return hydrated;
}

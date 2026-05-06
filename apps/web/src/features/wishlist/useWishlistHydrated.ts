import { useEffect, useState } from "react";

import { useWishlistStore } from "@/features/wishlist/store";

type WishlistStoreWithPersist = typeof useWishlistStore & {
  persist: {
    hasHydrated: () => boolean;
    onFinishHydration: (fn: () => void) => () => void;
  };
};

const store = useWishlistStore as WishlistStoreWithPersist;

/** `false` until persisted wishlist state has rehydrated from storage (avoid empty flash / layout jump). */
export function useWishlistHydrated(): boolean {
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

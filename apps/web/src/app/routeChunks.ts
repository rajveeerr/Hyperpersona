import type { ComponentType } from "react";

/**
 * Shared dynamic imports for route chunks — must stay in sync with `router.tsx` `lazy()` wiring
 * so Vite bundles match and `prefetch*()` warms the same assets as navigation.
 */
export const catalogPageImport = (): Promise<{ default: ComponentType }> =>
  import("@/pages/CatalogPage").then((m) => ({ default: m.CatalogPage }));

export const productPageImport = (): Promise<{ default: ComponentType }> =>
  import("@/pages/ProductPage").then((m) => ({ default: m.ProductPage }));

/** Warm catalog route chunk (e.g. PDP → Store). */
export const prefetchCatalogPageChunk = (): void => {
  void catalogPageImport();
};

/** Warm PDP shell chunk (e.g. catalog grid hover before click). */
export const prefetchProductPageChunk = (): void => {
  void productPageImport();
};

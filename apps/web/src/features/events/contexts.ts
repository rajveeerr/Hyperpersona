/**
 * Single source of truth for `/recommend?context=...` context strings.
 *
 * Spec rules (from `apps/web/event-types-description.md` §2):
 *   - Lowercase + underscores. No spaces, no caps, no special chars.
 *   - Use category slug, not SKU. The customer's stored facts in OpenSearch
 *     already know what they viewed; the context just tells the recommender
 *     which surface is rendering the slot.
 *   - No timestamps, no user IDs, no session IDs (these break caching for
 *     zero benefit — `customer_id` is already part of the cache key).
 *   - No cart contents, no exact prices.
 *
 * All callsites should use these helpers — never hand-build context strings.
 */

function normalize(slug: string): string {
  return slug
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export const Context = {
  homepage: () => "homepage",
  category: (slug: string) => `category:${normalize(slug)}`,
  productPage: (categorySlug: string) => `product_page:${normalize(categorySlug)}`,
  search: (categorySlug?: string) =>
    `search:${categorySlug ? normalize(categorySlug) : "general"}`,
  /**
   * Query-aware search context. The user's free-text `q` (and optional
   * facet filters) are normalized into the slug so the recommender can
   * use them as a category-ish hint, distinct from the generic
   * `search:general` "sponsored" slot. Stays under the `search:` surface
   * so the worker's `_build_rail_copy` already routes it correctly.
   */
  searchResults: (q: string, opts: { vertical?: string; freeDelivery?: boolean } = {}) => {
    const parts: string[] = [];
    if (q) parts.push(normalize(q));
    if (opts.vertical) parts.push(normalize(opts.vertical));
    if (opts.freeDelivery) parts.push("free_delivery");
    const slug = parts.filter(Boolean).join("_") || "general";
    return `search:${slug}`;
  },
  cartActive: () => "cart_active",
  cartEmpty: () => "cart_empty",
  postPurchase: () => "post_purchase",
  wishlist: () => "wishlist_active",
  orders: () => "orders_history",
  noResults: () => "no_results",
  emailNewsletter: () => "email:newsletter",
  emailCartRecovery: () => "email:cart_recovery",
} as const;

export type ContextString = ReturnType<(typeof Context)[keyof typeof Context]>;

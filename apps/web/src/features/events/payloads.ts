/**
 * Event payload helpers — a single source of truth for "what context goes
 * into a commerce event payload". Every page that fires `add_to_cart`,
 * `purchase`, `wishlist_add`, etc. should build its payload through these
 * helpers so the worker sees the same shape regardless of where the event
 * originated (PDP / cart / wishlist / recommendation rail / checkout).
 *
 * The companion in-memory snapshot cache exists because cart/wishlist line
 * objects ship a thin subset of fields (slug/name/image/unitPrice) — but
 * the same product just passed through the catalog grid or PDP fetch with
 * the full `Product` shape. We stamp the rich snapshot every time a
 * Product-like object renders, then read it back at remove/checkout time
 * so events carry brand/rating/freeDelivery/etc. without N+1 fetches.
 *
 * Cleared on logout via `clearProductSnapshotCache()` (see tracker/init.ts)
 * so cross-identity leak isn't possible.
 */

import type {
  CartLine,
  ComplementProduct,
  Product,
  ProductReview,
  RecommendProduct,
  ReviewHelpfulVote,
  WishlistLine,
} from "@/shared/api/contracts";

/**
 * Canonical product context for events. Required fields are everything
 * the spec lists as mandatory; optional fields are best-effort (filled
 * when the source object carries them or the snapshot cache has them).
 *
 * Field names use snake_case to match the BE wire convention for event
 * payloads (the worker reads them directly out of `payload`).
 */
export type ProductSnapshot = {
  product_id: string;
  product_name: string;
  category: string;
  /** Slug — useful for joining events back to catalog rows in analytics. */
  slug?: string;
  subcategory?: string;
  price: number;
  /** Pre-discount sticker price when the SKU is on sale. */
  compare_at?: number;
  brand?: string;
  vertical?: string;
  free_delivery?: boolean;
  rating?: number;
  review_count?: number;
  inventory_status?: string;
  personalization_tags?: string[];
  tags?: string[];
};

export type VariantSnapshot = {
  color?: string;
  size?: string;
  storage?: string;
  /** PDP swatch hue when there are no real variants — purely a preview hint. */
  preview_swatch?: string;
};

export type ReviewSnapshot = {
  review_id: string;
  rating: number;
  /** Optional title / headline. */
  title?: string;
  /** First N chars of the body — the worker can do its own truncation; we
   *  ship up to 600 chars so single-paragraph reviews are intact. */
  body: string;
  body_length: number;
  verified_purchase?: boolean;
  helpful_count?: number;
  not_helpful_count?: number;
};

// ---------------------------------------------------------------------------
// Snapshot cache — stamps the rich product context every time a Product
// flows through a render path (catalog grid, rec rail, PDP fetch, popular
// shelf, etc.) so cart/wishlist event sites can read it back later.

const cache = new Map<string, ProductSnapshot>();

function dropEmpty(snap: ProductSnapshot): ProductSnapshot {
  // Don't store undefined fields — keeps the cache compact and prevents
  // stale optionals from masking later, more complete observations.
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(snap)) {
    if (v !== undefined && v !== null && v !== "") out[k] = v;
  }
  return out as ProductSnapshot;
}

function mergeSnapshot(prev: ProductSnapshot | undefined, next: ProductSnapshot): ProductSnapshot {
  if (!prev) return next;
  // Later observations win when they carry a value; earlier observations
  // fill in any field the new one doesn't have. Result: a wishlist remove
  // that only knows id+price still gets brand/rating from the prior PDP view.
  return dropEmpty({ ...prev, ...next });
}

/** Stamp a single product into the cache. */
export function rememberProduct(snap: ProductSnapshot): void {
  if (!snap.product_id) return;
  cache.set(snap.product_id, mergeSnapshot(cache.get(snap.product_id), dropEmpty(snap)));
}

/**
 * Bulk variant. Accepts anything we can derive a snapshot from — full
 * `Product` rows, `RecommendProduct` rail items, or `ComplementProduct`
 * cart-rail items. Each input is normalized through the right adapter.
 */
export function rememberProducts(
  products: Array<Product | RecommendProduct | ComplementProduct> | undefined | null,
): void {
  if (!products) return;
  for (const p of products) {
    if ("id" in p) rememberProduct(productSnapshot(p));
    else if ("rank" in p && "image" in p) rememberProduct(fromRecommendProduct(p as RecommendProduct));
    else if ("rank" in p) rememberProduct(fromComplementProduct(p as ComplementProduct));
  }
}

/**
 * Read the cached snapshot for a productId. Returns `undefined` when the
 * product has never been seen on this device this session — callers should
 * fall back to whatever skinny fields they have in hand.
 */
export function getProductSnapshot(productId: string): ProductSnapshot | undefined {
  return cache.get(productId);
}

/** Wipe everything — call on logout / identity change. */
export function clearProductSnapshotCache(): void {
  cache.clear();
}

// ---------------------------------------------------------------------------
// Adapters — turn a source object into a ProductSnapshot.

export function productSnapshot(p: Product): ProductSnapshot {
  return dropEmpty({
    product_id: p.id,
    product_name: p.name,
    category: p.category,
    slug: p.slug,
    subcategory: p.department,
    price: p.price,
    compare_at: p.compareAt,
    brand: p.brand,
    vertical: p.vertical,
    free_delivery: p.freeDelivery,
    rating: p.rating,
    review_count: p.reviewCount,
    inventory_status: p.inventoryStatus,
    personalization_tags: p.personalizationTags,
    tags: p.tags,
  });
}

export function fromRecommendProduct(p: RecommendProduct): ProductSnapshot {
  return dropEmpty({
    product_id: p.product_id,
    product_name: p.name,
    category: p.category,
    price: p.price,
    compare_at: p.compareAt ?? undefined,
    brand: p.brand,
    vertical: p.vertical,
    rating: p.rating,
    review_count: p.reviewCount,
    inventory_status: p.inventoryStatus,
    personalization_tags: p.personalizationTags,
    tags: p.tags,
  });
}

export function fromComplementProduct(p: ComplementProduct): ProductSnapshot {
  return dropEmpty({
    product_id: p.product_id,
    product_name: p.name,
    category: p.category,
    price: p.price,
    vertical: p.vertical,
  });
}

/**
 * Build a snapshot from a CartLine. CartLine only carries
 * id/slug/name/image/unitPrice/quantity — for the rest we read the cache
 * stamped earlier in the session. Returns the merged result so the event
 * payload is as rich as possible.
 */
export function fromCartLine(line: CartLine): ProductSnapshot {
  const fromLine: ProductSnapshot = {
    product_id: line.productId,
    product_name: line.name,
    slug: line.slug,
    price: line.unitPrice,
    category: getProductSnapshot(line.productId)?.category ?? "",
  };
  return mergeSnapshot(getProductSnapshot(line.productId), dropEmpty(fromLine));
}

/** Wishlist counterpart — same merge pattern. */
export function fromWishlistLine(line: WishlistLine): ProductSnapshot {
  const fromLine: ProductSnapshot = {
    product_id: line.productId,
    product_name: line.name,
    slug: line.slug,
    price: line.unitPrice,
    category: getProductSnapshot(line.productId)?.category ?? "",
  };
  return mergeSnapshot(getProductSnapshot(line.productId), dropEmpty(fromLine));
}

// ---------------------------------------------------------------------------
// Variant + review adapters.

/**
 * Normalize the PDP `variantContext` ({color, size, storage, previewSwatch})
 * into a snake_case payload extra. Returns `undefined` when nothing was
 * picked so callers can drop the field entirely instead of shipping `{}`.
 */
export function variantSnapshot(ctx: Record<string, string> | undefined): VariantSnapshot | undefined {
  if (!ctx) return undefined;
  const out: VariantSnapshot = {};
  if (ctx.color) out.color = ctx.color;
  if (ctx.size) out.size = ctx.size;
  if (ctx.storage) out.storage = ctx.storage;
  if (ctx.previewSwatch) out.preview_swatch = ctx.previewSwatch;
  return Object.keys(out).length === 0 ? undefined : out;
}

const REVIEW_BODY_MAX = 600;

export function reviewSnapshot(review: ProductReview): ReviewSnapshot {
  const body = (review.body ?? "").trim();
  return {
    review_id: review.id,
    rating: review.rating,
    title: review.title,
    body: body.length > REVIEW_BODY_MAX ? `${body.slice(0, REVIEW_BODY_MAX - 1)}…` : body,
    body_length: body.length,
    verified_purchase: review.verifiedPurchase,
    helpful_count: review.helpfulCount,
    not_helpful_count: review.notHelpfulCount,
  };
}

/** Pure helper for the helpful-vote engagement payload. */
export function reviewVoteSnapshot(reviewId: string, vote: ReviewHelpfulVote): {
  review_id: string;
  vote: ReviewHelpfulVote;
} {
  return { review_id: reviewId, vote };
}

// ---------------------------------------------------------------------------
// Backwards-compat shims for the old productCategoryCache.ts API.

/** @deprecated — use `getProductSnapshot(id)?.category ?? ""` directly. */
export function getProductCategory(productId: string): string {
  return getProductSnapshot(productId)?.category ?? "";
}

/** @deprecated — use `clearProductSnapshotCache()` directly. */
export function clearProductCategoryCache(): void {
  clearProductSnapshotCache();
}

/** @deprecated — use `rememberProduct({ product_id, product_name, category, price })`. */
export function rememberProductCategory(productId: string, category: string | undefined | null): void {
  if (!productId || !category) return;
  rememberProduct({
    product_id: productId,
    category,
    // Required fields fall back to placeholder; mergeSnapshot keeps any
    // richer observation already in the cache.
    product_name: getProductSnapshot(productId)?.product_name ?? "",
    price: getProductSnapshot(productId)?.price ?? 0,
  });
}

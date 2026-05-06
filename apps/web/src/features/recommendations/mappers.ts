/**
 * Adapters from BE recommendation shapes → the canonical `Product` shape that
 * `ProductGrid`/`ProductCard` consume.
 *
 * `/recommend` ships everything the catalog ProductCard needs except
 * `description` and `features` (long-form copy not used in tile rendering),
 * so the conversion is mostly a rename of `product_id` → `id`/`slug`.
 *
 * `/recommend/complement` ships a much lighter shape (no image, no rating,
 * no brand) and is rendered through a different surface — see
 * `ComplementRail.tsx`. It does NOT flow through this mapper.
 */

import type { Product, RecommendProduct } from "@/shared/api/contracts";

export function recommendProductToProduct(item: RecommendProduct): Product {
  return {
    id: item.product_id,
    slug: item.product_id, // BE uses the slug as `product_id` in this response
    name: item.name,
    brand: item.brand,
    category: item.category,
    price: item.price,
    compareAt: item.compareAt ?? undefined,
    rating: item.rating,
    reviewCount: item.reviewCount,
    image: item.image,
    description: "",
    features: [],
    badges: item.badges,
    inventoryStatus: item.inventoryStatus,
    personalizationTags: item.personalizationTags,
    vertical: item.vertical as Product["vertical"],
    tags: item.tags,
  };
}

export function recommendProductsToProducts(items: RecommendProduct[]): Product[] {
  return items.map(recommendProductToProduct);
}

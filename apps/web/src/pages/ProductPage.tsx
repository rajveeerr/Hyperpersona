import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { EditorialProductDetail } from "@/features/catalog/components/EditorialProductDetail";
import { ProductDetailSkeleton } from "@/features/catalog/components/CatalogSkeletons";
import { useCartStore } from "@/features/cart/store";
import { Context } from "@/features/events/contexts";
import { useSpecTrack } from "@/features/events/specEvents";
import { usePdpDwell } from "@/features/events/usePdpDwell";
import { ProductSuggestionsSection } from "@/features/recommendations/components/ProductSuggestionsSection";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { pushToast } from "@/features/toast/store";
import { useWishlistStore } from "@/features/wishlist/store";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

function truncateToastLabel(name: string, max = 44) {
  const t = name.trim();
  return t.length <= max ? t : `${t.slice(0, max - 1)}…`;
}

export function ProductPage() {
  const { slug = "" } = useParams();
  const addItem = useCartStore((state) => state.addItem);
  const updateQuantity = useCartStore((state) => state.updateQuantity);
  const toggleWishlist = useWishlistStore((state) => state.toggle);
  const hasWishlist = useWishlistStore((state) => state.has);
  const trackSpec = useSpecTrack();

  const productQuery = useQuery({
    queryKey: ["product", slug],
    queryFn: () => apiClient.getProduct(slug),
  });
  const product = productQuery.data;
  const productCategory = product?.category ?? "";
  const productPageContext = productCategory ? Context.productPage(productCategory) : "";
  const recommendationsQuery = useQuery({
    queryKey: ["recommend", productPageContext],
    queryFn: () => apiClient.getRecommendation(productPageContext),
    enabled: productPageContext.length > 0,
  });

  // `product_view` (spec) — fire once per product mount. Re-fires when slug
  // changes (SPA nav between PDPs); the tracker dedup window already
  // guards against React StrictMode double-mount.
  const viewedSlugRef = useRef<string | null>(null);
  useEffect(() => {
    if (!product) return;
    if (viewedSlugRef.current === product.slug) return;
    viewedSlugRef.current = product.slug;
    trackSpec("product_view", {
      product_id: product.id,
      product_name: product.name,
      category: product.category,
      price: product.price,
    });
  }, [product, trackSpec]);

  // `product_dwell` — 10s threshold, once per page load, paused when tab hidden.
  usePdpDwell({
    product_id: product?.id ?? "",
    category: product?.category ?? "",
  });

  if (productQuery.isError) {
    return (
      <div className={tw.page}>
        <p className="text-sm text-red-800/90" role="alert">
          We could not load this product. It may have been removed or the link is incorrect.
        </p>
      </div>
    );
  }

  if (!product) {
    return (
      <div className={tw.stackLg}>
        <ProductDetailSkeleton />
        <ProductSuggestionsSection isLoading />
      </div>
    );
  }

  return (
    <div className="relative isolate flex flex-col gap-0">
      <EditorialProductDetail
        product={product}
        wishlisted={hasWishlist(product.id)}
        onAddToCart={(quantity) => {
          addItem(product);
          if (quantity > 1) {
            updateQuantity(product.id, quantity);
          }
          pushToast(
            quantity > 1
              ? `Bag updated · ${truncateToastLabel(product.name)} ×${quantity}`
              : `Added to bag · ${truncateToastLabel(product.name)}`,
          );
          trackSpec("add_to_cart", {
            product_id: product.id,
            product_name: product.name,
            category: product.category,
            price: product.price,
            quantity,
          });
        }}
        onWishlistToggle={() => {
          const removing = hasWishlist(product.id);
          toggleWishlist(product);
          pushToast(
            removing ? `Removed from wishlist · ${truncateToastLabel(product.name)}` : `Saved to wishlist · ${truncateToastLabel(product.name)}`,
          );
          if (removing) {
            trackSpec("wishlist_remove", {
              product_id: product.id,
              category: product.category,
            });
          } else {
            trackSpec("wishlist_add", {
              product_id: product.id,
              product_name: product.name,
              category: product.category,
            });
          }
        }}
      />
      <ProductSuggestionsSection isLoading={recommendationsQuery.isLoading}>
        {!recommendationsQuery.isLoading && !recommendationsQuery.data ? (
          <p className={`text-sm ${tw.muted}`}>No suggestion rails returned for this product yet.</p>
        ) : recommendationsQuery.data ? (
          <RecommendationRail
            rail={recommendationsQuery.data}
            sourceContext={productPageContext}
            presentation="pdp"
          />
        ) : null}
      </ProductSuggestionsSection>
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { EditorialProductDetail } from "@/features/catalog/components/EditorialProductDetail";
import { ProductDetailSkeleton } from "@/features/catalog/components/CatalogSkeletons";
import { useCartStore } from "@/features/cart/store";
import { useTrackEvent } from "@/features/events/useTrackEvent";
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
  const track = useTrackEvent();

  const productQuery = useQuery({
    queryKey: ["product", slug],
    queryFn: () => apiClient.getProduct(slug),
  });
  const recommendationsQuery = useQuery({
    queryKey: ["product-recommendations", slug],
    queryFn: () => apiClient.getSurfaceRecommendations("pdp", slug),
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

  if (!productQuery.data) {
    return (
      <div className={tw.stackLg}>
        <ProductDetailSkeleton />
        <ProductSuggestionsSection isLoading />
      </div>
    );
  }

  const product = productQuery.data;

  return (
    <div className="relative isolate flex flex-col gap-0">
      <EditorialProductDetail
        product={product}
        wishlisted={hasWishlist(product.id)}
        onAddToCart={(quantity, variantContext) => {
          addItem(product);
          if (quantity > 1) {
            updateQuantity(product.id, quantity);
          }
          pushToast(
            quantity > 1
              ? `Bag updated · ${truncateToastLabel(product.name)} ×${quantity}`
              : `Added to bag · ${truncateToastLabel(product.name)}`,
          );
          track({
            customer_id: "demo-customer-1",
            event_type: "add_to_cart",
            payload: {
              productId: product.id,
              slug: product.slug,
              quantity,
              selectedOptions: variantContext ?? {},
              freeDelivery: product.freeDelivery === true,
              vertical: product.vertical ?? "general",
            },
            consent_scope: ["analytics", "personalization"],
          });
        }}
        onWishlistToggle={() => {
          const removing = hasWishlist(product.id);
          toggleWishlist(product.id);
          pushToast(
            removing ? `Removed from wishlist · ${truncateToastLabel(product.name)}` : `Saved to wishlist · ${truncateToastLabel(product.name)}`,
          );
          track({
            customer_id: "demo-customer-1",
            event_type: removing ? "wishlist_remove" : "wishlist_add",
            payload: { productId: product.id, slug: product.slug },
            consent_scope: ["analytics", "personalization"],
          });
        }}
      />
      <ProductSuggestionsSection isLoading={recommendationsQuery.isLoading}>
        {!recommendationsQuery.isLoading &&
        (!recommendationsQuery.data || recommendationsQuery.data.length === 0) ? (
          <p className={`text-sm ${tw.muted}`}>No suggestion rails returned for this product yet.</p>
        ) : (
          recommendationsQuery.data?.map((rail) => (
            <RecommendationRail key={rail.id} rail={rail} presentation="pdp" />
          ))
        )}
      </ProductSuggestionsSection>
    </div>
  );
}

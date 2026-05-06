import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { EditorialProductDetail } from "@/features/catalog/components/EditorialProductDetail";
import { ProductDetailSkeleton } from "@/features/catalog/components/CatalogSkeletons";
import { useAddToCart } from "@/features/cart/useCart";
import { Context } from "@/features/events/contexts";
import {
  productSnapshot,
  rememberProduct,
  variantSnapshot,
} from "@/features/events/payloads";
import { useSpecTrack } from "@/features/events/specEvents";
import { usePdpDwell } from "@/features/events/usePdpDwell";
import { ProductSuggestionsSection } from "@/features/recommendations/components/ProductSuggestionsSection";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { recommendProductsToProducts } from "@/features/recommendations/mappers";
import { resolveRailCopy } from "@/features/recommendations/railCopy";
import { pushToast } from "@/features/toast/store";
import {
  useAddToWishlist,
  useIsInWishlist,
  useRemoveFromWishlist,
} from "@/features/wishlist/useWishlist";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

function truncateToastLabel(name: string, max = 44) {
  const t = name.trim();
  return t.length <= max ? t : `${t.slice(0, max - 1)}…`;
}

export function ProductPage() {
  const { slug = "" } = useParams();
  const trackSpec = useSpecTrack();
  const addToCart = useAddToCart();
  const addToWishlist = useAddToWishlist();
  const removeFromWishlist = useRemoveFromWishlist();
  // `useIsInWishlist` is a hook reading from React Query cache — call it
  // unconditionally and before any early returns. Empty productId is safe
  // (hook returns false for falsy ids).

  const productQuery = useQuery({
    queryKey: ["product", slug],
    queryFn: () => apiClient.getProduct(slug),
  });
  const product = productQuery.data;
  const wishlisted = useIsInWishlist(product?.id ?? "");
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
    // Stamp the full snapshot so cart/wishlist remove events later in the
    // session carry brand/rating/freeDelivery/etc. without re-fetching.
    rememberProduct(productSnapshot(product));
    if (viewedSlugRef.current === product.slug) return;
    viewedSlugRef.current = product.slug;
    trackSpec("product_view", productSnapshot(product));
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
        wishlisted={wishlisted}
        onAddToCart={(quantity, variantContext) => {
          const variant = variantSnapshot(variantContext);
          addToCart.mutate({
            productId: product.id,
            quantity,
            ...(variantContext && Object.keys(variantContext).length > 0
              ? { selectedOptions: variantContext }
              : {}),
          });
          pushToast(
            quantity > 1
              ? `Bag updated · ${truncateToastLabel(product.name)} ×${quantity}`
              : `Added to bag · ${truncateToastLabel(product.name)}`,
          );
          trackSpec("add_to_cart", {
            ...productSnapshot(product),
            quantity,
            source: "pdp",
            ...(variant ? { variant } : {}),
          });
        }}
        onWishlistToggle={(variantContext) => {
          const variant = variantSnapshot(variantContext);
          if (wishlisted) {
            removeFromWishlist.mutate(product.id);
            pushToast(`Removed from wishlist · ${truncateToastLabel(product.name)}`);
            trackSpec("wishlist_remove", productSnapshot(product));
          } else {
            addToWishlist.mutate({
              productId: product.id,
              productSnapshot: {
                slug: product.slug,
                name: product.name,
                image: product.image,
                unitPrice: product.price,
              },
            });
            pushToast(`Saved to wishlist · ${truncateToastLabel(product.name)}`);
            trackSpec("wishlist_add", {
              ...productSnapshot(product),
              source: "pdp",
              ...(variant ? { variant } : {}),
            });
          }
        }}
      />
      <ProductSuggestionsSection isLoading={recommendationsQuery.isLoading}>
        {!recommendationsQuery.isLoading &&
        (!recommendationsQuery.data || recommendationsQuery.data.products.length === 0) ? (
          <p className={`text-sm ${tw.muted}`}>No suggestion rails returned for this product yet.</p>
        ) : recommendationsQuery.data ? (
          (() => {
            const rail = resolveRailCopy(recommendationsQuery.data, {
              eyebrow: "Suggested next",
              headline: "Pieces that complete the story",
              subtitle: "Hand-picked complements to round out the look.",
              modeLabel: "Catalog pairings",
            });
            return (
              <RecommendationRail
                products={recommendProductsToProducts(recommendationsQuery.data.products)}
                sourceContext={productPageContext}
                title={rail.headline}
                subtitle={rail.eyebrow}
                reason={rail.subtitle}
                personalized={Boolean(recommendationsQuery.data.personalization_reason)}
                modeLabel={rail.mode_label}
                presentation="pdp"
              />
            );
          })()
        ) : null}
      </ProductSuggestionsSection>
    </div>
  );
}

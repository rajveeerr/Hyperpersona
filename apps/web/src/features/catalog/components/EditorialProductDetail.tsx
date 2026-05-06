import { useCallback, useEffect, useMemo, useState } from "react";

import { PdpProductHero } from "@/features/catalog/components/pdp/PdpProductHero";
import { PdpTabbedDetails } from "@/features/catalog/components/pdp/PdpTabbedDetails";
import {
  discountPercent,
  pdpCanvas,
  showStylingTab,
  type DetailTab,
} from "@/features/catalog/components/pdp/pdpShared";
import type { SwatchId } from "@/features/catalog/pdpSwatches";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import type { Product } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

type EditorialProductDetailProps = {
  product: Product;
  wishlisted: boolean;
  onAddToCart: (quantity: number, variantContext?: Record<string, string>) => void;
  onWishlistToggle: () => void;
};

export function EditorialProductDetail({
  product,
  wishlisted,
  onAddToCart,
  onWishlistToggle,
}: EditorialProductDetailProps) {
  const track = useTrackEvent();
  const [qty, setQty] = useState(1);
  const [swatch, setSwatch] = useState<SwatchId>("brick");
  const [activeImage, setActiveImage] = useState(0);
  const [tab, setTab] = useState<DetailTab>("description");

  const gallery = useMemo(() => {
    const rest = product.images ?? [];
    const merged = [product.image, ...rest];
    return merged.filter((url, i) => merged.indexOf(url) === i);
  }, [product.image, product.images]);

  const hasCatalogColors = (product.colorOptions?.length ?? 0) > 0;
  const hasSizes = (product.sizeOptions?.length ?? 0) > 0;
  const hasStorage = (product.storageOptions?.length ?? 0) > 0;

  const [colorId, setColorId] = useState(product.colorOptions?.[0]?.id ?? "");
  const [sizeId, setSizeId] = useState(product.sizeOptions?.[0]?.id ?? "");
  const [storageId, setStorageId] = useState(product.storageOptions?.[0]?.id ?? "");

  const activeSrc = gallery[activeImage] ?? product.image;
  const useHueFilter = !hasCatalogColors;

  const emitTab = useCallback(
    (next: DetailTab) => {
      setTab(next);
      track({
        customer_id: "demo-customer-1",
        event_type: "pdp_tab_selected",
        payload: { productId: product.id, slug: product.slug, tab: next },
        consent_scope: ["analytics", "personalization"],
      });
    },
    [product.id, product.slug, track],
  );

  const emitVariant = useCallback(
    (optionKind: "color" | "size" | "storage", optionId: string, optionLabel: string) => {
      track({
        customer_id: "demo-customer-1",
        event_type: "pdp_variant_selected",
        payload: { productId: product.id, slug: product.slug, optionKind, optionId, optionLabel },
        consent_scope: ["analytics", "personalization"],
      });
    },
    [product.id, product.slug, track],
  );

  useEffect(() => {
    setColorId(product.colorOptions?.[0]?.id ?? "");
    setSizeId(product.sizeOptions?.[0]?.id ?? "");
    setStorageId(product.storageOptions?.[0]?.id ?? "");
    setActiveImage(0);
    setQty(1);
    setTab("description");

    track({
      customer_id: "demo-customer-1",
      event_type: "product_pdp_viewed",
      payload: {
        productId: product.id,
        slug: product.slug,
        vertical: product.vertical ?? "general",
        freeDelivery: product.freeDelivery === true,
      },
      consent_scope: ["analytics", "personalization"],
    });
  }, [product.freeDelivery, product.id, product.slug, product.vertical, track]);

  const variantContext = useMemo(() => {
    const ctx: Record<string, string> = {};
    if (hasCatalogColors && colorId) ctx.color = colorId;
    if (hasSizes && sizeId) ctx.size = sizeId;
    if (hasStorage && storageId) ctx.storage = storageId;
    if (useHueFilter) ctx.previewSwatch = swatch;
    return ctx;
  }, [colorId, hasCatalogColors, hasSizes, hasStorage, sizeId, storageId, swatch, useHueFilter]);

  const bumpQty = (delta: number) => {
    setQty((q) => {
      const next = Math.min(20, Math.max(1, q + delta));
      if (next !== q) {
        track({
          customer_id: "demo-customer-1",
          event_type: "pdp_quantity_changed",
          payload: { productId: product.id, slug: product.slug, quantity: next },
          consent_scope: ["analytics", "personalization"],
        });
      }
      return next;
    });
  };

  const vertical = product.vertical ?? "general";

  const tabs = useMemo(() => {
    const rows: { id: DetailTab; label: string }[] = [{ id: "description", label: "Description" }];
    if (showStylingTab(product.vertical)) {
      rows.push({ id: "styling", label: "Styling ideas" });
    }
    rows.push({ id: "reviews", label: "Reviews" }, { id: "highlights", label: "Highlights" });
    return rows;
  }, [product.vertical]);

  const specLines = product.specification ?? [];
  const pctOff =
    product.compareAt != null && product.compareAt > product.price
      ? discountPercent(product.price, product.compareAt)
      : null;

  const onReportProduct = useCallback(() => {
    track({
      customer_id: "demo-customer-1",
      event_type: "pdp_report_product_clicked",
      payload: { productId: product.id, slug: product.slug },
      consent_scope: ["analytics", "personalization"],
    });
  }, [product.id, product.slug, track]);

  return (
    <section
      className={`relative z-0 ${tw.editorialBreakout} border-b border-outline/15 ${pdpCanvas}`}
      aria-labelledby="pdp-title"
    >
      <div className={`${tw.layoutFrame} pb-5 pt-8 sm:pb-6 sm:pt-10 lg:pb-6 lg:pt-12`}>
        <PdpProductHero
          product={product}
          vertical={vertical}
          gallery={gallery}
          activeImage={activeImage}
          setActiveImage={setActiveImage}
          activeSrc={activeSrc}
          useHueFilter={useHueFilter}
          swatch={swatch}
          setSwatch={setSwatch}
          hasCatalogColors={hasCatalogColors}
          colorId={colorId}
          setColorId={setColorId}
          hasSizes={hasSizes}
          sizeId={sizeId}
          setSizeId={setSizeId}
          hasStorage={hasStorage}
          storageId={storageId}
          setStorageId={setStorageId}
          emitVariant={emitVariant}
          pctOff={pctOff}
          qty={qty}
          bumpQty={bumpQty}
          onAddToCart={onAddToCart}
          variantContext={variantContext}
          wishlisted={wishlisted}
          onWishlistToggle={onWishlistToggle}
        />

        <PdpTabbedDetails
          product={product}
          vertical={vertical}
          tab={tab}
          tabs={tabs}
          specLines={specLines}
          emitTab={emitTab}
          onReportProduct={onReportProduct}
        />
      </div>
    </section>
  );
}

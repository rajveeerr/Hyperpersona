import { PdpBreadcrumb } from "@/features/catalog/components/pdp/PdpBreadcrumb";
import { PdpCommerceActions } from "@/features/catalog/components/pdp/PdpCommerceActions";
import { PdpGallery } from "@/features/catalog/components/pdp/PdpGallery";
import { PdpProductSummary } from "@/features/catalog/components/pdp/PdpProductSummary";
import { PdpVariantSelectors } from "@/features/catalog/components/pdp/PdpVariantSelectors";
import type { SwatchId } from "@/features/catalog/pdpSwatches";
import type { Product } from "@/shared/api/contracts";

export type PdpProductHeroProps = {
  product: Product;
  vertical: string;
  gallery: string[];
  activeImage: number;
  setActiveImage: (index: number) => void;
  activeSrc: string;
  useHueFilter: boolean;
  swatch: SwatchId;
  setSwatch: (id: SwatchId) => void;
  hasCatalogColors: boolean;
  colorId: string;
  setColorId: (id: string) => void;
  hasSizes: boolean;
  sizeId: string;
  setSizeId: (id: string) => void;
  hasStorage: boolean;
  storageId: string;
  setStorageId: (id: string) => void;
  emitVariant: (optionKind: "color" | "size" | "storage", optionId: string, optionLabel: string) => void;
  pctOff: number | null;
  qty: number;
  bumpQty: (delta: number) => void;
  onAddToCart: (quantity: number, variantContext?: Record<string, string>) => void;
  variantContext: Record<string, string>;
  wishlisted: boolean;
  onWishlistToggle: () => void;
};

export function PdpProductHero(props: PdpProductHeroProps) {
  const {
    product,
    vertical,
    gallery,
    activeImage,
    setActiveImage,
    activeSrc,
    useHueFilter,
    swatch,
    setSwatch,
    hasCatalogColors,
    colorId,
    setColorId,
    hasSizes,
    sizeId,
    setSizeId,
    hasStorage,
    storageId,
    setStorageId,
    emitVariant,
    pctOff,
    qty,
    bumpQty,
    onAddToCart,
    variantContext,
    wishlisted,
    onWishlistToggle,
  } = props;

  return (
    <>
      <PdpBreadcrumb product={product} />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1.08fr)_minmax(0,1fr)] lg:items-stretch lg:gap-x-12 xl:gap-x-16">
        <PdpGallery
          product={product}
          gallery={gallery}
          activeImage={activeImage}
          onSelectImage={setActiveImage}
          activeSrc={activeSrc}
          useHueFilter={useHueFilter}
          swatch={swatch}
        />

        <div className="flex min-h-0 flex-col gap-8 lg:border-l lg:border-outline/12 lg:pl-10 xl:pl-12">
          <PdpProductSummary product={product} vertical={vertical} pctOff={pctOff} />

          <PdpVariantSelectors
            product={product}
            hasCatalogColors={hasCatalogColors}
            colorId={colorId}
            setColorId={setColorId}
            swatch={swatch}
            setSwatch={setSwatch}
            hasSizes={hasSizes}
            sizeId={sizeId}
            setSizeId={setSizeId}
            hasStorage={hasStorage}
            storageId={storageId}
            setStorageId={setStorageId}
            emitVariant={emitVariant}
          />

          <PdpCommerceActions
            product={product}
            qty={qty}
            bumpQty={bumpQty}
            onAddToCart={onAddToCart}
            variantContext={variantContext}
            wishlisted={wishlisted}
            onWishlistToggle={onWishlistToggle}
          />
        </div>
      </div>
    </>
  );
}

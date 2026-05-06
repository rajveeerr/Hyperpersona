import { pdpSwatchFilters, type SwatchId } from "@/features/catalog/pdpSwatches";
import { imageInner, imageShell } from "@/features/catalog/components/pdp/pdpShared";
import type { Product } from "@/shared/api/contracts";

type PdpGalleryProps = {
  product: Product;
  gallery: string[];
  activeImage: number;
  onSelectImage: (index: number) => void;
  activeSrc: string;
  useHueFilter: boolean;
  swatch: SwatchId;
};

export function PdpGallery({
  product,
  gallery,
  activeImage,
  onSelectImage,
  activeSrc,
  useHueFilter,
  swatch,
}: PdpGalleryProps) {
  return (
    <div className={imageShell}>
      <div className={imageInner}>
        <figure className="m-0 w-full max-w-[min(100%,28rem)]">
          <div className="drop-shadow-[0_36px_72px_rgba(34,28,23,0.12)]">
            <img
              src={activeSrc}
              alt={product.name}
              width={900}
              height={1012}
              sizes="(max-width: 1024px) min(92vw, 28rem), min(28rem, 36vw)"
              decoding="async"
              fetchPriority={activeImage === 0 ? "high" : "low"}
              style={useHueFilter ? { filter: pdpSwatchFilters[swatch] } : undefined}
              className="mx-auto h-auto max-h-[min(46vh,480px)] w-auto max-w-full object-contain transition-[filter,opacity] duration-500 ease-out will-change-[filter]"
            />
          </div>
        </figure>
      </div>
      {gallery.length > 1 ? (
        <div
          className="flex shrink-0 gap-2 overflow-x-auto border-t border-outline/10 bg-white/35 px-3 py-3 sm:px-4"
          role="tablist"
          aria-label="Product gallery"
        >
          {gallery.map((src, i) => (
            <button
              key={`${src}-${i}`}
              type="button"
              role="tab"
              aria-selected={i === activeImage}
              onClick={() => onSelectImage(i)}
              className={`relative size-16 shrink-0 overflow-hidden rounded-md ring-1 ring-offset-2 ring-offset-[#e8e4de] transition-shadow sm:size-17 ${
                i === activeImage ? "ring-ink/45 shadow-md" : "ring-outline/30 hover:ring-ink/20"
              }`}
            >
              <img
                src={src}
                alt=""
                className="size-full object-cover"
                width={120}
                height={120}
                loading="lazy"
                decoding="async"
              />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

import { pdpSwatches, type SwatchId } from "@/features/catalog/pdpSwatches";
import { optionIdle, optionSelected } from "@/features/catalog/components/pdp/pdpShared";
import type { Product } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

type PdpVariantSelectorsProps = {
  product: Product;
  hasCatalogColors: boolean;
  colorId: string;
  setColorId: (id: string) => void;
  swatch: SwatchId;
  setSwatch: (id: SwatchId) => void;
  hasSizes: boolean;
  sizeId: string;
  setSizeId: (id: string) => void;
  hasStorage: boolean;
  storageId: string;
  setStorageId: (id: string) => void;
  emitVariant: (optionKind: "color" | "size" | "storage", optionId: string, optionLabel: string) => void;
};

export function PdpVariantSelectors({
  product,
  hasCatalogColors,
  colorId,
  setColorId,
  swatch,
  setSwatch,
  hasSizes,
  sizeId,
  setSizeId,
  hasStorage,
  storageId,
  setStorageId,
  emitVariant,
}: PdpVariantSelectorsProps) {
  return (
    <div className="grid gap-8 rounded-xl border border-outline/18 bg-white/50 p-5 shadow-[0_16px_48px_rgba(34,28,23,0.04)] backdrop-blur-xs sm:p-6 lg:gap-9">
      {hasCatalogColors ? (
        <div>
          <div className="mb-2 flex items-baseline justify-between gap-2">
            <p className={`text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Color</p>
          </div>
          <div className="flex flex-wrap gap-2" role="list" aria-label="Color options">
            {product.colorOptions!.map((opt) => {
              const selected = opt.id === colorId;
              return (
                <button
                  key={opt.id}
                  type="button"
                  role="listitem"
                  onClick={() => {
                    setColorId(opt.id);
                    emitVariant("color", opt.id, opt.label);
                  }}
                  className={`rounded-pill border px-3 py-2 text-left text-[0.8125rem] font-medium transition-transform duration-150 ${
                    selected ? optionSelected : optionIdle
                  }`}
                  aria-pressed={selected}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <div>
          <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Colour</p>
          <div className="flex flex-wrap items-center gap-2.5" role="list" aria-label="Colour preview">
            {pdpSwatches.map((s) => {
              const selected = s.id === swatch;
              return (
                <button
                  key={s.id}
                  type="button"
                  role="listitem"
                  onClick={() => {
                    setSwatch(s.id);
                    emitVariant("color", s.id, s.label);
                  }}
                  className={`size-9 shrink-0 rounded-full border-2 transition-transform duration-150 ${s.bg} ${
                    selected
                      ? "scale-105 border-accent-strong shadow-[0_2px_14px_rgba(143,80,50,0.22)]"
                      : "border-outline/45 opacity-90 hover:scale-105 hover:border-ink/25"
                  }`}
                  aria-pressed={selected}
                  aria-label={`Preview ${s.label}`}
                />
              );
            })}
          </div>
          <p className={`mt-2 text-[0.7rem] ${tw.muted}`}>Preview tint — catalog colors ship on select SKUs.</p>
        </div>
      )}

      {hasSizes ? (
        <div>
          <div className="mb-2 flex items-baseline justify-between gap-2">
            <p className={`text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Size</p>
            <span className={`text-[0.65rem] font-medium uppercase tracking-ui-wide ${tw.muted}`}>Size guide (soon)</span>
          </div>
          <div className="flex flex-wrap gap-2" role="list" aria-label="Size options">
            {product.sizeOptions!.map((opt) => {
              const selected = opt.id === sizeId;
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => {
                    setSizeId(opt.id);
                    emitVariant("size", opt.id, opt.label);
                  }}
                  className={`min-h-10 min-w-10 rounded-md border px-3 py-2 text-sm font-semibold tabular-nums transition-transform duration-150 ${
                    selected ? optionSelected : optionIdle
                  }`}
                  aria-pressed={selected}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {hasStorage ? (
        <div>
          <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Storage</p>
          <div className="flex flex-wrap gap-2" role="list" aria-label="Storage options">
            {product.storageOptions!.map((opt) => {
              const selected = opt.id === storageId;
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => {
                    setStorageId(opt.id);
                    emitVariant("storage", opt.id, opt.label);
                  }}
                  className={`rounded-pill border px-4 py-2 text-[0.8125rem] font-semibold transition-transform duration-150 ${
                    selected ? optionSelected : optionIdle
                  }`}
                  aria-pressed={selected}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

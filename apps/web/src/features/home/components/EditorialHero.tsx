import { useState } from "react";
import { Link } from "react-router-dom";

import { pdpSwatchFilters, pdpSwatches, type SwatchId } from "@/features/catalog/pdpSwatches";
import { tw } from "@/shared/ui/tw";

/**
 * Hero product — RGBA WebP in `public/hero-product-cutout.webp` (true transparency).
 * Replace that file to swap SKU; keep ~900px wide max for performance.
 */
const HERO_PRODUCT_IMG = "/hero-product-cutout.webp";

/**
 * Editorial PDP hero: radial cream ground, centered transparent product cutout,
 * bottom row — category + title | swatches + size | copy + qty + add (reference layout).
 */
export const EditorialHero = () => {
  const [qty, setQty] = useState(1);
  const [swatch, setSwatch] = useState<SwatchId>("brick");

  return (
    <section
      className={`${tw.editorialBreakout} border-b border-[#e5e5e5] bg-[radial-gradient(ellipse_82%_78%_at_50%_36%,#fdfbf7_0%,#f5f2ed_48%,#e9e3da_100%)] text-ink`}
      aria-labelledby="hero-product-title"
    >
      <div
        className={`${tw.layoutFrame} flex min-h-[min(88vh,920px)] flex-col pb-10 pt-5 sm:pb-12 sm:pt-6 lg:pb-14 lg:pt-8`}
      >
        {/* Center — single SKU, alpha channel so only the product reads (ref Sonnette stack) */}
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center py-4 sm:py-6">
          <figure className="relative mx-auto w-full max-w-[min(440px,90vw)] sm:max-w-[min(520px,85vw)]">
            <div className="drop-shadow-[0_40px_80px_rgba(34,28,23,0.14)]">
              <img
                src={HERO_PRODUCT_IMG}
                alt="Highland organic matelasse throw, folded — product cutout"
                width={900}
                height={785}
                fetchPriority="high"
                decoding="async"
                style={{ filter: pdpSwatchFilters[swatch] }}
                className="mx-auto h-[min(58vh,600px)] w-auto max-w-full object-contain transition-[filter] duration-500 ease-out will-change-[filter]"
              />
            </div>
          </figure>
        </div>

        {/* Bottom PDP row */}
        <div className="mt-auto grid gap-10 border-t border-outline/15 pt-10 sm:gap-12 sm:pt-12 lg:grid-cols-3 lg:items-end lg:gap-8 lg:pt-14">
          <div className="min-w-0 text-left">
            <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Throw</p>
            <h1
              id="hero-product-title"
              className={`${tw.displayProductTitle} text-[clamp(2rem,4.2vw,3.35rem)]`}
            >
              Highland Organic Matelasse Throw
            </h1>
          </div>

          <div className="flex flex-col items-start gap-3 lg:items-center lg:text-center">
            <div className="flex items-center gap-2.5" role="list" aria-label="Color">
              {pdpSwatches.map((s) => {
                const selected = s.id === swatch;
                return (
                  <button
                    key={s.id}
                    type="button"
                    role="listitem"
                    onClick={() => setSwatch(s.id)}
                    className={`size-9 shrink-0 rounded-full border-2 transition-transform duration-150 ${s.bg} ${
                      selected
                        ? "scale-105 border-ink/55 shadow-[0_0_0_1px_rgba(34,28,23,0.12)]"
                        : "border-outline/45 opacity-90 hover:scale-105 hover:border-ink/25"
                    }`}
                    aria-pressed={selected}
                    aria-label={`Colour ${s.label}`}
                  />
                );
              })}
            </div>
            <p className={`text-[0.8125rem] tracking-[0.02em] ${tw.muted}`}>Size: 50&quot; × 70&quot;</p>
          </div>

          <div className="min-w-0 text-left lg:text-left">
            <p className={`max-w-md text-pretty text-sm leading-relaxed sm:text-[0.9375rem] sm:leading-relaxed ${tw.muted}`}>
              The soft, rippled weave keeps a pliable drape that settles in over time light enough for warm nights,
              substantial enough when the air turns cool.
            </p>
            <div className="mt-6 flex min-w-0 flex-wrap items-center gap-3 sm:gap-4">
              <div className={tw.qtyStepper} aria-label="Quantity">
                <button
                  type="button"
                  className={tw.qtyStepperBtn}
                  onClick={() => setQty((q) => Math.max(1, q - 1))}
                  aria-label="Decrease quantity"
                >
                  −
                </button>
                <span className={tw.qtyStepperValue}>{qty}</span>
                <button
                  type="button"
                  className={tw.qtyStepperBtn}
                  onClick={() => setQty((q) => Math.min(20, q + 1))}
                  aria-label="Increase quantity"
                >
                  +
                </button>
              </div>
              <Link to="/catalog" className={tw.buttonEditorialBag}>
                Add to bag — $98
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

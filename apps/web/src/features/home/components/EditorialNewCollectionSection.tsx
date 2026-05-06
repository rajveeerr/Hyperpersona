import { Link } from "react-router-dom";

import { prefetchCatalogPageChunk, prefetchProductPageChunk } from "@/app/routeChunks";
import { formatCurrency } from "@/shared/lib/format";
import { tw } from "@/shared/ui/tw";

const BASE = "/collection-new";

/** Single studio mat + 1px hairlines (reference: warm bone field, barely-there dividers). */
const surface = "bg-[#f2f0ec]";
/** Divider color visible in `gap-px` gutters only. */
const hairline = "bg-[#e5e5e5]";

const tiles = [
  {
    id: "tile-jacket",
    label: "Altitude shell",
    price: 220,
    slug: "altitude-shell-jacket",
    src: `${BASE}/grid-jacket.webp`,
    alt: "Front-facing jacket, transparent cutout",
  },
  {
    id: "tile-hoodie",
    label: "Recovery knit hoodie",
    price: 88,
    slug: "recovery-knit-hoodie",
    src: `${BASE}/grid-hoodie.webp`,
    alt: "Front-facing hoodie, transparent cutout",
  },
  {
    id: "tile-pants",
    label: "Metro knit pant",
    price: 95,
    slug: "metro-knit-pant",
    src: `${BASE}/grid-pants.webp`,
    alt: "Flat lay denim jeans, transparent cutout",
  },
  {
    id: "tile-beanie",
    label: "Trail watch beanie",
    price: 24,
    slug: "trail-watch-beanie",
    src: `${BASE}/grid-beanie.webp`,
    alt: "Front-facing beanie, transparent cutout",
  },
] as const;

export function EditorialNewCollectionSection() {
  return (
    <section
      aria-labelledby="new-collection-heading"
      className={`${tw.editorialBreakout} border-b border-[#e5e5e5] ${surface} antialiased`}
    >
      <div className={`${tw.layoutFrame} w-full py-10 sm:py-12 lg:py-14`}>
        <div className={`grid w-full overflow-hidden lg:grid-cols-2 lg:items-stretch lg:gap-px ${hairline}`}>
          {/* Lifestyle — spans full layout rail width with hero typography */}
          <Link
            to="/catalog"
            prefetch="intent"
            className={`group relative isolate flex min-h-[min(48vh,22rem)] overflow-hidden sm:min-h-[min(52vh,26rem)] lg:min-h-[min(56vh,32rem)] ${surface}`}
            onMouseEnter={prefetchCatalogPageChunk}
            onFocus={prefetchCatalogPageChunk}
          >
            <img
              src={`${BASE}/lifestyle-model.webp`}
              alt="Editorial portrait for new collection"
              width={1600}
              height={1067}
              loading="lazy"
              decoding="async"
              className="absolute inset-0 size-full object-cover object-[center_25%] transition-[transform,filter] duration-700 ease-out motion-reduce:transition-none group-hover:scale-[1.04] group-hover:brightness-[1.05] motion-reduce:group-hover:scale-100 motion-reduce:group-hover:brightness-100"
            />
            <div
              className="pointer-events-none absolute inset-0 bg-linear-to-t from-[rgba(34,28,23,0.58)] via-[rgba(34,28,23,0.14)] to-transparent group-hover:from-[rgba(34,28,23,0.48)] group-hover:via-outline"
              aria-hidden
            />
            <div className="relative z-1 mt-auto flex flex-col justify-end p-6 sm:p-8 lg:p-10">
              <p className="mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.2em] text-white/88 transition-[color,letter-spacing] duration-500 ease-out group-hover:text-white group-hover:tracking-[0.22em]">
                Just in
              </p>
              <h2
                id="new-collection-heading"
                className="max-w-[12ch] font-display text-[clamp(2rem,5vw,3.5rem)] font-normal leading-[0.98] tracking-display-tight text-balance text-[#fdfbf7] antialiased transition-[transform,color] duration-500 ease-out will-change-transform motion-reduce:transition-none group-hover:translate-x-1 group-hover:text-white motion-reduce:group-hover:translate-x-0"
              >
                New collection
              </h2>
              <p className="mt-3 max-w-sm text-pretty text-sm leading-relaxed text-white/82 transition-colors duration-500 group-hover:text-white/92">
                Isolated cutouts on a quiet mat—editorial portrait on the left, ghost products on the right.
              </p>
            </div>
          </Link>

          {/* 2×2 — lookbook grid: label top-left, price bottom-right, product centered */}
          <div className={`grid min-h-0 grid-cols-2 grid-rows-2 gap-px ${hairline} lg:min-h-0`}>
            {tiles.map((tile) => (
              <article
                key={tile.id}
                className={`group relative min-h-56 sm:min-h-64 ${surface} transition-[background-color,box-shadow] duration-300 ease-out motion-reduce:transition-none hover:bg-[#eae8e2] focus-within:bg-[#eae8e2] motion-reduce:hover:bg-[#f2f0ec] motion-reduce:focus-within:bg-[#f2f0ec]`}
              >
                <Link
                  to={`/products/${tile.slug}`}
                  prefetch="intent"
                  className="relative flex size-full min-h-0 flex-col outline-offset-2 focus-visible:outline-2 focus-visible:outline-accent"
                  onMouseEnter={prefetchProductPageChunk}
                  onFocus={prefetchProductPageChunk}
                >
                  <span className="pointer-events-none absolute left-4 top-4 z-1 max-w-[min(72%,11rem)] font-body text-[0.625rem] font-medium uppercase leading-[1.15] tracking-[0.2em] text-ink/90 transition-[color,letter-spacing] duration-300 ease-out group-hover:text-ink group-hover:tracking-[0.22em] group-focus-within:text-ink group-focus-within:tracking-[0.22em] sm:left-5 sm:top-5 sm:max-w-52 sm:text-[0.6875rem]">
                    {tile.label}
                  </span>
                  <div className="flex flex-1 items-center justify-center px-5 pt-15 pb-17 sm:px-6 sm:pb-18 sm:pt-16 lg:px-7 lg:pb-20 lg:pt-17">
                    <img
                      src={tile.src}
                      alt={tile.alt}
                      width={900}
                      height={900}
                      loading="lazy"
                      decoding="async"
                      className="max-h-[min(12rem,44vw)] w-auto max-w-[88%] object-contain object-center drop-shadow-[0_6px_18px_rgba(22,18,15,0.04)] transition-[transform,filter] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] will-change-transform motion-reduce:transition-none motion-reduce:group-hover:translate-y-0 motion-reduce:group-hover:scale-100 motion-reduce:group-focus-within:translate-y-0 motion-reduce:group-focus-within:scale-100 group-hover:-translate-y-0.5 group-hover:scale-[1.025] group-hover:drop-shadow-[0_10px_28px_rgba(22,18,15,0.07)] group-focus-within:-translate-y-0.5 group-focus-within:scale-[1.025] group-focus-within:drop-shadow-[0_10px_28px_rgba(22,18,15,0.07)] sm:max-h-[min(14rem,38vw)] lg:max-h-[min(16rem,24vw)]"
                    />
                  </div>
                  <span className="pointer-events-none absolute bottom-4 right-4 z-1 font-body text-[0.8125rem] font-medium tabular-nums tracking-[0.02em] text-ink/90 transition-colors duration-300 group-hover:text-ink group-focus-within:text-ink sm:bottom-5 sm:right-5">
                    {formatCurrency(tile.price)}
                  </span>
                </Link>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

import { tw } from "@/shared/ui/tw";

/** Distinct from `EditorialHero` throw — front studio jacket packshot (RGBA), same grid vocabulary as `/catalog`. */
const PRE_FOOTER_IMG = "/collection-new/grid-jacket.webp";

/**
 * Sonnette-style closing band on `/` — white field, wordmark + links, then centered cutout above
 * centered display copy before the global footer.
 */
export function HomeEditorialClosingSection() {
  return (
    <section
      aria-labelledby="home-closing-heading"
      className={`${tw.storyCanvas} ${tw.editorialBreakout} border-b border-[#e5e5e5] text-ink antialiased`}
    >
      <div className={`${tw.layoutFrame} py-12 sm:py-14 lg:py-20`}>
        <div className="mx-auto flex w-full max-w-3xl flex-col items-center gap-8 text-center sm:gap-10 lg:max-w-4xl lg:gap-12">
          <figure className="w-full max-w-[min(18rem,72vw)] shrink-0">
            <img
              src={PRE_FOOTER_IMG}
              alt="Quilted jacket, front studio packshot — product cutout"
              width={1000}
              height={1000}
              loading="lazy"
              decoding="async"
              className="mx-auto h-auto w-full max-w-[16rem] object-contain drop-shadow-[0_28px_56px_rgba(34,28,23,0.1)] sm:max-w-[18rem]"
            />
          </figure>
          <h2
            id="home-closing-heading"
            className={`max-w-[min(32ch,92vw)] font-display text-[clamp(2.1rem,5.2vw,3.65rem)] font-normal leading-[0.98] tracking-display-tight text-balance`}
          >
            Quiet grid, clear consent, and a calmer reason for every pick—one edit before you sign off for the night.
          </h2>
        </div>
      </div>
    </section>
  );
}

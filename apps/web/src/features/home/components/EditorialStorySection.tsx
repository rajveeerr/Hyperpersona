import { Link } from "react-router-dom";

import { tw } from "@/shared/ui/tw";

const INLINE_IMG =
  "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=480&h=280&q=80";

/**
 * Post-hero editorial band: display headline with inline image + aside (reference layout).
 * Uses `storyCanvas` (white) for a hard edge against the warm cream hero.
 */
export function EditorialStorySection() {
  return (
    <section
      aria-labelledby="editorial-story-heading"
      className={`${tw.storyCanvas} ${tw.editorialBreakout} border-b border-outline/15 py-14 sm:py-16 lg:py-20`}
    >
      <div className={tw.layoutFrame}>
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1.12fr)_minmax(0,0.44fr)] lg:items-end lg:gap-x-14 xl:gap-x-20">
          <div className="min-w-0">
            <h2 id="editorial-story-heading" className={tw.editorialStoryHeadline}>
              <span className="block">We spend one third</span>
              <span className="mt-1 block sm:mt-1.5">of our lives sleeping.</span>
              <span className="mt-2 block sm:mt-2.5">
                <span className="inline-grid max-w-full grid-cols-[auto_auto_auto] items-end gap-x-2.5 sm:gap-x-3.5">
                  <span className="self-end leading-none">So we</span>
                  <img
                    src={INLINE_IMG}
                    alt="Bed with soft linens and bedside table, cropped"
                    width={176}
                    height={104}
                    loading="lazy"
                    decoding="async"
                    className="h-[2.65rem] w-[4.35rem] shrink-0 self-end rounded-sm object-cover shadow-[0_8px_24px_rgba(34,28,23,0.1)] sm:h-[3.35rem] sm:w-[5.4rem]"
                  />
                  <span className="self-end leading-none">decided</span>
                </span>
              </span>
              <span className="mt-1 block leading-[1.02] sm:mt-1.5">to make it memorable.</span>
            </h2>
          </div>

          <aside className="flex min-w-0 flex-col gap-6 lg:max-w-88 lg:justify-self-end xl:max-w-96">
            <p className={`text-pretty text-sm leading-relaxed sm:text-[0.95rem] sm:leading-relaxed ${tw.muted}`}>
              {
                "Today, there are a million reasons keeping people up at night—we're here to make restful sleep simple again."
              }
            </p>
            <Link
              to="/catalog"
              className={`${tw.buttonGhost} w-fit min-w-34 justify-center border-ink/20 text-[0.8125rem] font-semibold tracking-wide hover:border-ink/45`}
            >
              Shop now
            </Link>
          </aside>
        </div>
      </div>
    </section>
  );
}

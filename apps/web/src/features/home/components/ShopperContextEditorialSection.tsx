import { Link } from "react-router-dom";

import { PersonaSwitcher } from "@/features/personas/components/PersonaSwitcher";
import { SessionMemoryCard } from "@/features/session-memory/components/SessionMemoryCard";
import { tw } from "@/shared/ui/tw";

/** Local WebPs — Unsplash License; originals: photo-1483985988355-763728e1935b, photo-1607082348824-0a96f2a4b9da, photo-1523381210434-271e8be1f52b */
const IMG_INLINE = "/lab-inline-chip.webp";
const IMG_RETAIL = "/lab-context-retail.webp";
const IMG_SIGNALS = "/lab-context-signals.webp";

const labHeadline =
  "font-display font-normal tracking-display-tight text-balance text-ink antialiased leading-[1.02] text-[clamp(2.15rem,5.4vw,4.1rem)]";

const photoMat =
  "overflow-hidden rounded-sm bg-hero-canvas ring-1 ring-outline/15 shadow-[0_16px_40px_rgba(34,28,23,0.07)]";

const labShell =
  "rounded-[1.2rem] border border-outline/14 bg-white/70 p-6 shadow-[0_28px_72px_rgba(34,28,23,0.042)] backdrop-blur-[8px] sm:rounded-[1.3rem] sm:p-8 lg:p-10";

const railEyebrow = `text-[0.7rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`;

/**
 * Profile lab — one shared mat (headline + still-life + controls) so the story and the demo surface read as a
 * single unit; persona list and session read-out share one inner frame (`UI_REFERENCE` hand-off before footer).
 */
export function ShopperContextEditorialSection() {
  return (
    <section
      aria-labelledby="shopper-context-heading"
      className={`${tw.storyCanvas} ${tw.editorialBreakout} border-b border-[#e5e5e5] pt-8 pb-10 sm:pt-10 sm:pb-12 lg:pt-11 lg:pb-14`}
    >
      <div className={tw.layoutFrame}>
        <p className={`mb-5 text-[0.7rem] font-semibold uppercase tracking-[0.18em] sm:mb-6 ${tw.muted}`}>
          Profile lab
        </p>

        <div className={labShell}>
          <div className="grid gap-10 lg:grid-cols-2 lg:items-start lg:gap-x-10 xl:gap-x-14">
            {/* Story column — same rhythm as personalized / hero editorial */}
            <div className="flex min-h-0 flex-col gap-6 sm:gap-7">
              <h2 id="shopper-context-heading" className={labHeadline}>
                <span className="block">Pick who is shopping.</span>
                <span className="mt-1 block sm:mt-1.5">Memory follow along.</span>
                <span className="mt-2 block sm:mt-2.5">
                  <span className="inline-grid max-w-full grid-cols-[auto_auto_auto] items-end gap-x-2.5 sm:gap-x-3.5">
                    <span className="self-end leading-none">So we</span>
                    <img
                      src={IMG_INLINE}
                      alt=""
                      width={200}
                      height={133}
                      loading="lazy"
                      decoding="async"
                      className="h-[2.65rem] w-auto max-w-18 shrink-0 self-end object-cover object-center shadow-[0_6px_18px_rgba(34,28,23,0.1)] sm:h-[3.35rem] sm:max-w-22"
                    />
                    <span className="self-end leading-none">read signals</span>
                  </span>
                </span>
                <span className="mt-1 block leading-[1.02] sm:mt-1.5">as they land.</span>
              </h2>

              <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:max-w-lg lg:gap-4" aria-hidden>
                <figure className={`m-0 ${photoMat}`}>
                  <img
                    src={IMG_RETAIL}
                    alt=""
                    width={960}
                    height={640}
                    loading="lazy"
                    decoding="async"
                    className="aspect-4/3 h-auto max-h-36 w-full object-cover sm:max-h-40 lg:max-h-44"
                  />
                </figure>
                <figure className={`m-0 ${photoMat}`}>
                  <img
                    src={IMG_SIGNALS}
                    alt=""
                    width={960}
                    height={640}
                    loading="lazy"
                    decoding="async"
                    className="aspect-4/3 h-auto max-h-36 w-full object-cover sm:max-h-40 lg:max-h-44"
                  />
                </figure>
              </div>
            </div>

            {/* Control column — hairline stack; persona + inference = one inner card */}
            <div className="flex min-h-0 flex-col lg:border-l lg:border-outline/12 lg:pl-10 xl:pl-12">
              <div className="pb-6 sm:pb-7">
                <p className={`${railEyebrow} mb-3`}>How it works</p>
                <ol className="list-decimal space-y-2.5 pl-4 text-sm leading-snug text-ink/90 sm:text-[0.9375rem] sm:leading-relaxed">
                  <li className="text-pretty pl-1 marker:font-medium marker:text-ink">
                    Choose a profile below—each one models a different kind of shopper.
                  </li>
                  <li className="text-pretty pl-1 marker:font-medium marker:text-ink">
                    Watch rails, copy, and the session read-out update together while you stay on this tab.
                  </li>
                  <li className="text-pretty pl-1 marker:font-medium marker:text-ink">
                    On a product page, read reviews, load more, vote helpful or not helpful, or write your own star
                    rating—those signals appear in the live event stream when personalization is allowed.
                  </li>
                </ol>
              </div>

              <div className="border-t border-outline/10 pt-6 sm:pt-7">
                <p className={`${railEyebrow} mb-3`}>Profiles</p>
                <p id="profiles-session-desc" className="sr-only">
                  Choose a profile, then read the live session summary underneath the same card.
                </p>
                <div
                  className="overflow-hidden rounded-md border border-outline/12 bg-white/55 shadow-[0_10px_32px_rgba(34,28,23,0.04)]"
                  aria-describedby="profiles-session-desc"
                >
                  <PersonaSwitcher embedded />
                  <SessionMemoryCard embedded />
                </div>
              </div>

              <div className="border-t border-outline/10 pt-6 sm:pt-7">
                <Link
                  to="/profile"
                  className={`${tw.buttonGhost} w-full justify-center border-ink/22 text-[0.8125rem] font-semibold tracking-wide hover:border-ink/45`}
                >
                  Open profile lab
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

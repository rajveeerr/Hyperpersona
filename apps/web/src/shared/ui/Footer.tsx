import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { useTrackEvent } from "@/features/events/useTrackEvent";
import { tw } from "@/shared/ui/tw";

/** RGBA WebP in `public/footer-product-mark.webp` — floating commerce mark (ref feather). */
const FOOTER_MARK_IMG = "/footer-product-mark.webp";

const footerLink =
  "text-[0.8125rem] font-normal leading-[2] text-ink/88 transition-opacity hover:opacity-60";

const linkColumns: { links: { label: string; to: string }[] }[] = [
  {
    links: [
      { label: "About HyperPersona", to: "/" },
      { label: "Store", to: "/catalog" },
      { label: "Gift card", to: "/catalog" },
    ],
  },
  {
    links: [
      { label: "Contact us", to: "/search" },
      { label: "Privacy policy", to: "/consent" },
      { label: "Terms and conditions", to: "/consent" },
      { label: "Legal notice", to: "/profile" },
    ],
  },
  {
    links: [
      { label: "Our guides", to: "/catalog" },
      { label: "Choosing your bedding", to: "/catalog" },
      { label: "Our expertise", to: "/profile" },
    ],
  },
];

/**
 * Editorial footer — Sonnette-style: mark, serif headline, email line,
 * three quiet link columns, mega wordmark clipped at bottom edge.
 */
export function Footer() {
  const track = useTrackEvent();

  function onNewsletterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "").trim();
    if (!email) return;
    track({
      event_type: "newsletter_interest",
      payload: { email, source: "footer" },
      consent_scope: ["analytics", "personalization"],
    });
    event.currentTarget.reset();
  }

  return (
    <footer
      className={`${tw.heroCanvas} ${tw.editorialBreakout} mt-auto border-t border-outline/20`}
      role="contentinfo"
    >
      <div className={`${tw.layoutFrame} pb-0 pt-14 sm:pt-16 lg:pt-16`}>
        {/* Upper band — centered like reference */}
        <div className="flex flex-col items-center text-center">
          <div className="mb-8 drop-shadow-[0_14px_32px_rgba(34,28,23,0.09)] sm:mb-10" aria-hidden>
            <img
              src={FOOTER_MARK_IMG}
              alt=""
              width={320}
              height={320}
              loading="lazy"
              decoding="async"
              className="mx-auto h-19 w-auto max-w-[min(10rem,65vw)] object-contain opacity-[0.9] sm:h-32"
            />
          </div>

          <h2 className={`${tw.displayNewsletterHeading} max-w-lg px-2 text-[clamp(2rem,3vw,1.95rem)]`}>
            Your home will love following us.
          </h2>

          <form onSubmit={onNewsletterSubmit} className="mt-9 w-full max-w-md sm:mt-10" aria-label="Newsletter signup">
            <label className="sr-only" htmlFor="footer-email">
              Email address
            </label>
            <div className="flex items-end gap-2 border-b border-ink/22 pb-2 transition-colors focus-within:border-ink/48">
              <input
                id="footer-email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder="Enter your email…"
                className="min-w-0 flex-1 border-0 bg-transparent py-1 text-left text-[0.875rem] text-ink outline-none placeholder:text-muted/50"
              />
              <button
                type="submit"
                className="shrink-0 cursor-pointer rounded-sm px-1 py-1 text-lg text-ink/80 transition-opacity hover:opacity-70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                aria-label="Submit email"
              >
                →
              </button>
            </div>
          </form>
        </div>

        {/* Link columns — ref: three blocks, sentence case, generous line height */}
        <nav
          className="mx-auto mt-20 grid max-w-4xl grid-cols-1 gap-12 text-center sm:mt-24 sm:grid-cols-3 sm:gap-10 sm:text-left"
          aria-label="Footer links"
        >
          {linkColumns.map((col, colIndex) => (
            <ul key={colIndex} className="list-none space-y-0 p-0">
              {col.links.map((item) => (
                <li key={item.to + item.label}>
                  <Link to={item.to} className={footerLink}>
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          ))}
        </nav>
      </div>

      {/* Mega wordmark — intentional slight clip at bottom (ref sonnette) */}
      <div className="relative mt-20 w-full overflow-hidden pb-0 sm:mt-24">
        <div className="relative mx-auto h-[clamp(3.35rem,10.5vw,5.75rem)] max-w-[100vw] sm:h-[clamp(3.85rem,9.5vw,6.25rem)]">
          <p
            className={`${tw.displayWordmarkFooter} absolute bottom-0 left-1/2 w-[108%] max-w-none -translate-x-1/2 translate-y-[26%] text-center text-[clamp(3.5rem,17vw,11.5rem)] leading-[0.72] sm:translate-y-[28%]`}
            aria-hidden
          >
            hyperpersona
          </p>
        </div>
        <span className="sr-only">HyperPersona</span>
      </div>
    </footer>
  );
}

import type { ReactNode } from "react";

import { tw } from "@/shared/ui/tw";

type HomePersonalizedSectionProps = {
  /** Storytelling mode for fallback/cold-start messaging in Phase 2. */
  mode?: "loading" | "personalized" | "generic" | "cold-start";
  children: ReactNode;
};

/**
 * Wraps personalized recommendation rails — `storyCanvas` stripe; on home it sits after hero / new
 * collection / popular, with **Profile lab** (`ShopperContextEditorialSection`) pulled **below** this block
 * so the lab lands just before the footer (UI_REFERENCE).
 */
export function HomePersonalizedSection({ children, mode = "personalized" }: HomePersonalizedSectionProps) {
  const showFallbackCallout = mode === "generic" || mode === "cold-start";
  return (
    <section
      className={`${tw.storyCanvas} ${tw.editorialBreakout} border-b border-[#e5e5e5] py-10 sm:py-12 lg:py-14`}
    >
      <div className={tw.layoutFrame}>
        {showFallbackCallout ? (
          <div className="mb-8 rounded-card border border-dashed border-ink/30 bg-white/55 px-4 py-3.5 sm:mb-10 sm:px-5 sm:py-4">
            <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>Fallback mode</p>
            <p className="mt-1.5 text-sm leading-relaxed text-ink/88">
              {mode === "generic"
                ? "These rails are currently generic. Personalization consent appears off or limited, so ranking confidence is intentionally conservative."
                : "Signals are still sparse, so the experience is in cold-start fallback. As search/click/cart events accumulate, reasons and confidence should sharpen."}
            </p>
          </div>
        ) : null}
        <div className="flex flex-col gap-14 sm:gap-16 lg:gap-20">{children}</div>
      </div>
    </section>
  );
}

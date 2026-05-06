import type { ReactNode } from "react";

import { PdpSuggestionsRailsSkeleton } from "@/features/catalog/components/CatalogSkeletons";
import { tw } from "@/shared/ui/tw";

/** Matches `HomePopularSection` / `HomePersonalizedSection` — UI_REFERENCE serif block. */
const sectionTitle =
  "font-display font-normal tracking-display-tight text-balance text-ink antialiased leading-[1.02] text-[clamp(1.85rem,3.8vw,2.85rem)]";

type ProductSuggestionsSectionProps = {
  children?: ReactNode;
  isLoading?: boolean;
};

/**
 * PDP “suggested next” band — alternates after the cream PDP hero (`EditorialProductDetail`) using `storyCanvas`,
 * same editorial breakout + frame rhythm as the home landing personalized strip.
 */
export function ProductSuggestionsSection({ children, isLoading }: ProductSuggestionsSectionProps) {
  return (
    <section
      className={`relative z-[2] ${tw.storyCanvas} ${tw.editorialBreakout} border-b border-outline/15 pb-10 pt-5 sm:pb-12 sm:pt-6 lg:pb-14 lg:pt-7`}
      aria-labelledby="pdp-suggestions-heading"
    >
      <div className={tw.layoutFrame}>
        <header className="mb-8 max-w-3xl sm:mb-10">
          <p className={`mb-3 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Suggested next</p>
          <h2 id="pdp-suggestions-heading" className={sectionTitle}>
            <span className="block">Pieces that complete</span>
            <span className="mt-1 block sm:mt-1.5">the story.</span>
          </h2>
          <p
            className={`mt-4 max-w-xl text-pretty text-sm leading-relaxed sm:mt-5 sm:text-[0.9375rem] sm:leading-relaxed ${tw.muted}`}
          >
            The same recommendation rails as the home landing—plain-language reasons, confidence when personalization
            is on, and the same transparent `ProductGrid` + tiles as `/catalog` so photography stays gallery-forward.
          </p>
        </header>
        <div className="flex flex-col gap-14 sm:gap-16 lg:gap-20">
          {isLoading ? <PdpSuggestionsRailsSkeleton /> : children}
        </div>
      </div>
    </section>
  );
}

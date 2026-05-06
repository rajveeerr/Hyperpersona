import type { ReactNode } from "react";

import { PdpSuggestionsRailsSkeleton } from "@/features/catalog/components/CatalogSkeletons";
import { tw } from "@/shared/ui/tw";

type ProductSuggestionsSectionProps = {
  children?: ReactNode;
  isLoading?: boolean;
};

/**
 * PDP “suggested next” band — alternates after the cream PDP hero (`EditorialProductDetail`) using `storyCanvas`,
 * same editorial breakout + frame rhythm as the home landing personalized strip. The eyebrow/headline/subtitle
 * now live on the inner `RecommendationRail` so they can be driven by the `/recommend` rail copy.
 */
export function ProductSuggestionsSection({ children, isLoading }: ProductSuggestionsSectionProps) {
  return (
    <section
      className={`relative z-[2] ${tw.storyCanvas} ${tw.editorialBreakout} border-b border-outline/15 pb-10 pt-5 sm:pb-12 sm:pt-6 lg:pb-14 lg:pt-7`}
      aria-label="Suggested next"
    >
      <div className={tw.layoutFrame}>
        <div className="flex flex-col gap-14 sm:gap-16 lg:gap-20">
          {isLoading ? <PdpSuggestionsRailsSkeleton /> : children}
        </div>
      </div>
    </section>
  );
}

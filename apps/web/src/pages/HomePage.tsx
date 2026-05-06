import { useQuery } from "@tanstack/react-query";

import { EditorialHero } from "@/features/home/components/EditorialHero";
import { EditorialNewCollectionSection } from "@/features/home/components/EditorialNewCollectionSection";
import { HomePersonalizedSection } from "@/features/home/components/HomePersonalizedSection";
import { HomePopularSection } from "@/features/home/components/HomePopularSection";
import { HomeEditorialClosingSection } from "@/features/home/components/HomeEditorialClosingSection";
import { ShopperContextEditorialSection } from "@/features/home/components/ShopperContextEditorialSection";
import { Context } from "@/features/events/contexts";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { recommendProductsToProducts } from "@/features/recommendations/mappers";
import { resolveRailCopy } from "@/features/recommendations/railCopy";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

export function HomePage() {
  const homepageContext = Context.homepage();
  const recommendationsQuery = useQuery({
    queryKey: ["recommend", homepageContext],
    queryFn: () => apiClient.getRecommendation(homepageContext),
  });

  const personalized = Boolean(recommendationsQuery.data?.personalization_reason);
  const recommendationMode: "loading" | "personalized" | "generic" | "cold-start" =
    recommendationsQuery.isLoading || recommendationsQuery.isPending
      ? "loading"
      : !recommendationsQuery.data || recommendationsQuery.data.products.length === 0
        ? "cold-start"
        : personalized
          ? "personalized"
          : "generic";

  return (
    <div className="flex flex-col gap-0">
      <EditorialHero />

      <EditorialNewCollectionSection />

      <HomePopularSection />

      <HomePersonalizedSection mode={recommendationMode}>
        {recommendationsQuery.isLoading ? (
          <p className={`text-sm ${tw.muted}`}>Loading personalized picks…</p>
        ) : recommendationsQuery.data && recommendationsQuery.data.products.length > 0 ? (
          (() => {
            const rail = resolveRailCopy(recommendationsQuery.data, {
              eyebrow: "Recommended for you",
              headline: "Picks shaped by your signals",
              subtitle: "A starting point — your tiles will personalize as you browse.",
              modeLabel: "Editor's picks",
            });
            return (
              <RecommendationRail
                products={recommendProductsToProducts(recommendationsQuery.data.products)}
                sourceContext={homepageContext}
                title={rail.headline}
                subtitle={rail.eyebrow}
                reason={rail.subtitle}
                personalized={personalized}
                modeLabel={rail.mode_label}
                presentation="editorial"
              />
            );
          })()
        ) : null}
      </HomePersonalizedSection>

      {/* Profile lab then Sonnette-style closing strip before the global footer */}
      <ShopperContextEditorialSection />
      <HomeEditorialClosingSection />
    </div>
  );
}

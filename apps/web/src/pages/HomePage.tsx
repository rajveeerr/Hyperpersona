import { useQuery } from "@tanstack/react-query";

import { EditorialHero } from "@/features/home/components/EditorialHero";
import { EditorialNewCollectionSection } from "@/features/home/components/EditorialNewCollectionSection";
import { HomePersonalizedSection } from "@/features/home/components/HomePersonalizedSection";
import { HomePopularSection } from "@/features/home/components/HomePopularSection";
import { HomeEditorialClosingSection } from "@/features/home/components/HomeEditorialClosingSection";
import { ShopperContextEditorialSection } from "@/features/home/components/ShopperContextEditorialSection";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

export function HomePage() {
  const recommendationsQuery = useQuery({
    queryKey: ["home-recommendations"],
    queryFn: apiClient.getHomeRecommendations,
  });

  const recommendationMode: "loading" | "personalized" | "generic" | "cold-start" =
    recommendationsQuery.isLoading || recommendationsQuery.isPending
      ? "loading"
      : !recommendationsQuery.data || recommendationsQuery.data.length === 0
        ? "cold-start"
        : recommendationsQuery.data.every((rail) => rail.fallback)
          ? "generic"
          : "personalized";

  return (
    <div className="flex flex-col gap-0">
      <EditorialHero />

      <EditorialNewCollectionSection />

      <HomePopularSection />

      <HomePersonalizedSection mode={recommendationMode}>
        {recommendationsQuery.isLoading ? (
          <p className={`text-sm ${tw.muted}`}>Loading personalized picks…</p>
        ) : (
          recommendationsQuery.data?.map((rail) => (
            <RecommendationRail key={rail.id} rail={rail} presentation="editorial" />
          ))
        )}
      </HomePersonalizedSection>

      {/* Profile lab then Sonnette-style closing strip before the global footer */}
      <ShopperContextEditorialSection />
      <HomeEditorialClosingSection />
    </div>
  );
}

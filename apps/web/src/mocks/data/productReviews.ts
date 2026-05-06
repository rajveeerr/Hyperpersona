import type { ProductReview } from "@/shared/api/contracts";

/** Static seed keyed by product `slug` — MSW clones into mutable store per session. */
export const seedReviewsBySlug: Record<string, ProductReview[]> = {
  "commuter-sling-pack": [
    {
      id: "rev-csp-1",
      productId: "prod-3",
      authorDisplayName: "Alex M.",
      rating: 5,
      title: "Daily driver",
      body: "Fits a 13\" laptop without feeling bulky. Magnetic clasp is satisfying.",
      createdAt: "2025-10-12T10:00:00.000Z",
      verifiedPurchase: true,
      helpfulCount: 14,
      notHelpfulCount: 1,
      viewerHelpfulVote: null,
    },
    {
      id: "rev-csp-2",
      productId: "prod-3",
      authorDisplayName: "Sam R.",
      rating: 4,
      body: "Canvas is water-resistant as advertised. Wish the strap had one more notch.",
      createdAt: "2025-09-03T15:30:00.000Z",
      verifiedPurchase: true,
      helpfulCount: 6,
      notHelpfulCount: 2,
      viewerHelpfulVote: null,
    },
  ],
  "altitude-shell-jacket": [
    {
      id: "rev-asj-1",
      productId: "prod-1",
      authorDisplayName: "Jordan P.",
      rating: 5,
      title: "Held up in sleet",
      body: "Breathable enough for climbs, still blocks wind on ridgelines.",
      createdAt: "2025-11-20T09:00:00.000Z",
      verifiedPurchase: true,
      helpfulCount: 22,
      notHelpfulCount: 0,
      viewerHelpfulVote: null,
    },
  ],
};

import { products } from "@/mocks/data/products";
import type { RecommendationRail } from "@/shared/api/contracts";

export const homeRails: RecommendationRail[] = [
  {
    id: "home-1",
    title: "Picked for your active commute",
    subtitle: "Updated after your last search and bag wishlist activity.",
    reason: "Your recent signals lean toward weatherproof layers and compact carry.",
    confidence: 0.91,
    fallback: false,
    products: [products[0], products[2], products[3]],
  },
  {
    id: "home-2",
    title: "Add-on gear you are likely to convert on",
    subtitle: "Lower-ticket products paired with products already viewed.",
    reason: "These items complement your trail and daily-carry interests.",
    confidence: 0.84,
    fallback: false,
    products: [products[6], products[7], products[5]],
  },
];

export const productRails: RecommendationRail[] = [
  {
    id: "pdp-1",
    title: "Pairings shoppers add next",
    subtitle: "From the same trail-and-layer signals as home.",
    reason:
      "Socks, shells, and recovery layers that historically convert after footwear views—quiet add-ons with high attach rate.",
    confidence: 0.79,
    fallback: false,
    products: [products[6], products[0], products[5]],
  },
  {
    id: "pdp-2",
    title: "Room and desk adjacencies",
    subtitle: "When the PDP skews home or tech.",
    reason:
      "Lighting, seating, and pocket tech that share cart journeys with mixed-category shoppers—useful for demos that hop verticals.",
    confidence: 0.72,
    fallback: false,
    products: [products[10], products[11], products[12]],
  },
];

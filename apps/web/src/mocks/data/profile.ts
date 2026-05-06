import type { ConsentRecord, ExplanationRecord, ProfileSummary } from "@/shared/api/contracts";

/**
 * Default consent for the legacy demo customer (before auth was wired). New
 * authenticated sessions start with **no** consent record on file — see the
 * GET /api/consent handler which returns 404 in that case.
 */
export const initialConsent: ConsentRecord = {
  customer_id: "demo-customer-1",
  scopes: ["analytics", "personalization"],
  data_retention_days: 90,
  last_updated: new Date().toISOString(),
};

export const initialProfile: ProfileSummary = {
  customerId: "demo-customer-1",
  name: "Ava Chen",
  segment: "Performance commuter",
  topCategories: ["city-commute", "trail-running"],
  explicitPreferences: [
    { key: "fit", label: "Preferred fit", value: "Tailored but relaxed" },
    { key: "budget", label: "Budget band", value: "$80-$220" },
  ],
  inferredInterests: [
    { id: "interest-1", label: "Weather-ready gear", confidence: 0.92, source: "Viewed shell jackets twice" },
    { id: "interest-2", label: "Trail accessories", confidence: 0.78, source: "Searched for socks and light packs" },
    { id: "interest-3", label: "Desk-to-gym utility", confidence: 0.71, source: "Repeated city commute category visits" },
  ],
  recentSignals: [
    "searched for waterproof layers",
    "added shoes to cart",
    "saved a commuter bag to wishlist",
  ],
  lastUpdated: new Date().toISOString(),
};

export const explanationRecord: ExplanationRecord = {
  search: [
    "Outdoor affinity boosted weatherproof products.",
    "Recent searches increased trail accessory relevance.",
  ],
  recommendations: [
    "Home rail uses recent browsing, category affinity, and price comfort zone.",
    "Related items prioritize complementary gear from the same use case.",
  ],
  profileSignals: [
    "Explicit budget preference keeps premium overages limited.",
    "Recent activity favors weather-ready and trail gear.",
  ],
};

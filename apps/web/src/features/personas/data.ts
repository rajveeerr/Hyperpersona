export type DemoPersona = {
  id: string;
  name: string;
  /** Two-letter badge for the profile picker. */
  initials: string;
  label: string;
  summary: string;
  recentSignals: string[];
  currentIntent: string;
};

export const demoPersonas: DemoPersona[] = [
  {
    id: "budget-shopper",
    name: "Mia",
    initials: "MI",
    label: "Budget shopper",
    summary: "Value-conscious and promotion-sensitive, but still active across apparel and accessories.",
    recentSignals: ["sorted by price low to high", "saved commuter pants", "searched for under $100"],
    currentIntent: "Looking for affordable everyday essentials with versatile use.",
  },
  {
    id: "premium-buyer",
    name: "Ava",
    initials: "AV",
    label: "Premium buyer",
    summary: "Prefers premium materials, refined silhouettes, and high-confidence recommendations.",
    recentSignals: ["revisited premium shell", "opened profile lab", "viewed editorial recommendations"],
    currentIntent: "Comparing quality-first options and expects recommendations to feel curated.",
  },
  {
    id: "gift-shopper",
    name: "Ethan",
    initials: "ET",
    label: "Gift shopper",
    summary: "Browsing outside usual patterns with less stable intent and more exploratory clicks.",
    recentSignals: ["searched for gifts", "bounced across categories", "opened wishlist repeatedly"],
    currentIntent: "Trying to find a safe gift choice without strong product knowledge.",
  },
];

export const defaultPersona = demoPersonas[2];

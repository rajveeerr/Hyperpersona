/** Shared PDP colour story — hero + product detail (editorial commerce). */

export type SwatchId = "violet" | "brick" | "navy";

export const pdpSwatches: { id: SwatchId; label: string; bg: string }[] = [
  { id: "violet", label: "Violet", bg: "bg-[#4f2d58]" },
  { id: "brick", label: "Crimson", bg: "bg-[#7a1818]" },
  { id: "navy", label: "Navy", bg: "bg-[#1a2d4a]" },
];

export const pdpSwatchFilters: Record<SwatchId, string> = {
  violet: "hue-rotate(258deg) saturate(1.22) brightness(0.86) contrast(1.05)",
  brick: "hue-rotate(318deg) saturate(1.32) brightness(0.86) contrast(1.06)",
  navy: "hue-rotate(188deg) saturate(1.15) brightness(0.8) contrast(1.08)",
};

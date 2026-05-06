import type { Product } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

export type DetailTab = "description" | "styling" | "reviews" | "highlights";

/** Same radial mat as `EditorialHero` — UI_REFERENCE: warm ivory / parchment story. */
export const pdpCanvas =
  "bg-[radial-gradient(ellipse_82%_78%_at_50%_36%,#fdfbf7_0%,#f5f2ed_48%,#e9e3da_100%)] text-ink";

export const imageShell =
  "relative flex h-full min-h-[min(52vh,480px)] w-full flex-col overflow-hidden rounded-xl bg-[#e8e4de]/88 ring-1 ring-outline/10 shadow-[0_20px_60px_rgba(34,28,23,0.06)] lg:min-h-[min(58vh,560px)]";
export const imageInner =
  "flex min-h-0 flex-1 flex-col items-center justify-center px-4 py-8 sm:px-6 sm:py-10";

export const tabPill =
  "min-h-10 cursor-pointer rounded-pill border px-4 text-center text-[0.65rem] font-semibold uppercase tracking-ui-wide transition-[background-color,border-color,color,transform] duration-150 motion-reduce:transition-none";

export const optionSelected =
  "border-ink/30 bg-surface-strong text-ink shadow-[0_6px_20px_rgba(34,28,23,0.07)] ring-1 ring-inset ring-white/65";
export const optionIdle =
  "border-outline/55 bg-white/75 text-ink hover:-translate-y-px hover:border-ink/25";

export const specRow =
  "grid gap-1 border-b border-outline/12 py-4 last:border-b-0 sm:grid-cols-[minmax(0,10rem)_1fr] sm:gap-6";
export const specDt = `text-[0.7rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`;
export const specDd = "text-sm leading-relaxed text-ink/90 sm:text-[0.9375rem]";

export function discountPercent(price: number, compare: number) {
  return Math.round(((compare - price) / compare) * 100);
}

export function formatCategoryLabel(categorySlug: string) {
  return categorySlug
    .split("-")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** “Styling ideas” is apparel-only; other verticals get category-accurate tabs instead. */
export function showStylingTab(vertical: Product["vertical"]) {
  return vertical === "apparel";
}

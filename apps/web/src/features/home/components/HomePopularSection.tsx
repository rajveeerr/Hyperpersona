import { useQuery } from "@tanstack/react-query";

import { ProductGrid } from "@/features/catalog/components/ProductGrid";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

/** Matches hero / PDP editorial cream radial — UI_REFERENCE warm ivory band. */
const popularCanvas =
  "bg-[radial-gradient(ellipse_78%_72%_at_42%_40%,#fdfbf7_0%,#f5f2ed_46%,#e9e3da_100%)]";

const sectionTitle =
  "font-display font-normal tracking-display-tight text-balance text-ink antialiased leading-[1.02] text-[clamp(1.85rem,3.8vw,2.85rem)]";

/**
 * Static “most popular” rail — same catalog ordering for every shopper (not personalized).
 * Visual rhythm: editorial breakout + cream radial like `EditorialHero`, micro-label stack like profile lab.
 */
export function HomePopularSection() {
  const popularQuery = useQuery({
    queryKey: ["catalog-popular"],
    queryFn: apiClient.getPopularProducts,
  });

  if (!popularQuery.data?.length) {
    return popularQuery.isLoading ? (
      <section
        className={`${tw.editorialBreakout} border-b border-[#e5e5e5] ${popularCanvas} py-12 sm:py-14`}
        aria-labelledby="popular-heading"
      >
        <div className={tw.layoutFrame}>
          <p className={`text-sm ${tw.muted}`}>Loading most popular…</p>
        </div>
      </section>
    ) : null;
  }

  return (
    <section
      className={`${tw.editorialBreakout} border-b border-[#e5e5e5] ${popularCanvas} py-10 sm:py-12 lg:py-14`}
      aria-labelledby="popular-heading"
    >
      <div className={tw.layoutFrame}>
        <header className="mb-8 max-w-3xl sm:mb-10">
          <p className={`mb-3 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Most popular</p>
          <h2 id="popular-heading" className={sectionTitle}>
            <span className="block">What everyone is</span>
            <span className="mt-1 block sm:mt-1.5">reaching for right now.</span>
          </h2>
          <p className={`mt-4 max-w-xl text-pretty text-sm leading-relaxed sm:mt-5 sm:text-[0.9375rem] sm:leading-relaxed ${tw.muted}`}>
            A single, shared bestseller list from the catalog same for every shopper, refreshed from the server so
            demos stay grounded in real inventory signals.
          </p>
        </header>
        <ProductGrid products={popularQuery.data} />
      </div>
    </section>
  );
}

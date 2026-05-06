import { memo } from "react";
import { useSearchParams } from "react-router-dom";

import { SearchPageListing } from "@/pages/SearchPageListing";
import { tw } from "@/shared/ui/tw";

/** Editorial intro — depends only on `q`, so filter/sort/page URL changes do not re-render this block. */
const SearchPageIntro = memo(function SearchPageIntro({ q }: { q: string }) {
  return (
    <header className="max-w-3xl">
      <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Search</p>
      <h1 className={`${tw.storyTitle} max-w-[22ch]`}>{q ? `Results for “${q}”` : "Search the catalog"}</h1>
      {q ? (
        <p className={`mt-4 max-w-2xl text-sm leading-relaxed ${tw.muted}`}>
          Ranking reflects your consent scope and recent signals the explainability panel below is how HyperPersona
          surfaces why a result set is personalized or generic for this query.
        </p>
      ) : (
        <p className={`mt-4 max-w-2xl text-sm leading-relaxed ${tw.muted}`}>
          Submit a query from the header to see catalog search with the same grid, filters, and pagination as browse.
        </p>
      )}
    </header>
  );
});

export function SearchPage() {
  const [params] = useSearchParams();
  const q = (params.get("q") ?? "").trim();

  const shellMin =
    q.length > 0 ? "min-h-[min(76vh,880px)]" : "min-h-[min(52vh,560px)]";

  return (
    <div className={`${tw.stackLg} ${shellMin} pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
      <SearchPageIntro q={q} />

      {!q ? (
        <p className={`text-sm ${tw.muted}`}>Search for products to see ranking behavior.</p>
      ) : (
        <SearchPageListing />
      )}
    </div>
  );
}

import { tw } from "@/shared/ui/tw";

const pulseBar = "animate-pulse rounded-md bg-ink/6";

export function SearchInsightPanelSkeleton() {
  return (
    <section className={`${tw.labPanel} ${tw.labPanelPad}`} aria-busy aria-label="Loading search explainability">
      <div className="flex flex-col gap-5 sm:gap-6">
        <div className={`h-3 w-40 max-w-full ${pulseBar}`} />
        <div className={`h-9 w-full max-w-xl ${pulseBar}`} />
        <div className="h-px w-full max-w-md bg-ink/6" aria-hidden />
        <ul className={`${tw.stackSm} m-0 list-none p-0`}>
          <li className={`h-3.5 w-full max-w-2xl ${pulseBar}`} />
          <li className={`h-3.5 w-[92%] max-w-2xl ${pulseBar}`} />
          <li className={`h-3.5 w-[78%] max-w-2xl ${pulseBar}`} />
        </ul>
      </div>
    </section>
  );
}

type SearchInsightPanelProps = {
  personalized: boolean;
  query: string;
  explanations: string[];
  rankingContextChange?: {
    source: "consent" | "profile";
    at: string;
  } | null;
};

export const SearchInsightPanel = ({
  personalized,
  query,
  explanations,
  rankingContextChange = null,
}: SearchInsightPanelProps) => {
  const titleId = "search-insight-title";
  return (
    <section
      className={`${tw.labPanel} ${tw.labPanelPad}`}
      aria-labelledby={titleId}
    >
      <div className="flex flex-col gap-5 sm:gap-6">
        <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>
          Search explainability
        </p>
        <h2
          id={titleId}
          className={`${tw.displayH2} max-w-[36ch] text-[clamp(1.35rem,2.5vw,1.85rem)] font-medium leading-[1.12]`}
        >
          {personalized ? `Results for “${query}” are being re-ranked` : "Results are generic right now"}
        </h2>
        {rankingContextChange ? (
          <div className="rounded-card border border-outline/30 bg-white/65 px-4 py-3">
            <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>Ranking context updated</p>
            <p className="mt-1 text-sm leading-relaxed text-ink/88">
              {rankingContextChange.source === "consent"
                ? "Consent settings changed recently, so ranking behavior may shift between personalized and generic modes."
                : "Profile preferences changed recently, so ranking and recommendation explanations may update."}
            </p>
            <p className={`mt-1 text-[0.72rem] tabular-nums ${tw.muted}`}>
              {new Date(rankingContextChange.at).toLocaleTimeString(undefined, {
                hour: "numeric",
                minute: "2-digit",
                second: "2-digit",
              })}
            </p>
          </div>
        ) : null}
        <div className="border-t border-outline/20 pt-5 sm:pt-6">
          <p className={`mb-3 text-[0.7rem] font-medium uppercase tracking-ui-wide ${tw.muted}`}>
            Why this ranking
          </p>
          <ul className="m-0 grid list-none gap-3.5 p-0">
            {explanations.map((item) => (
              <li key={item} className="flex gap-3 text-[0.8125rem] leading-relaxed tracking-body text-ink/88">
                <span
                  className="mt-[0.5em] h-1 w-1 shrink-0 rounded-full bg-accent/55"
                  aria-hidden
                />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
};

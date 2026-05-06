import type { ExplanationRecord, ProfileSummary as ProfileSummaryType } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

const labelSerif = "font-display text-[1.05rem] font-normal tracking-display text-ink antialiased";

const fieldLabel = `text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`;

function formatCategorySlug(slug: string) {
  return slug
    .split("-")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

type ProfileSummaryProps = {
  profile: ProfileSummaryType;
  explanations?: ExplanationRecord | null;
  explanationsLoading?: boolean;
  explanationsError?: boolean;
};

export function ProfileSummary({
  profile,
  explanations,
  explanationsLoading,
  explanationsError,
}: ProfileSummaryProps) {
  return (
    <div className="grid gap-6 lg:gap-8">
      <div className="grid gap-6 lg:grid-cols-2">
        <section className={`${tw.labPanel} ${tw.labPanelPad} flex flex-col gap-5`}>
          <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Shopper lens</p>
          <h2 className={`${tw.displayH2} text-[clamp(1.45rem,2.8vw,2rem)] font-medium leading-snug`}>
            {profile.segment}
          </h2>
          <p className={`text-sm ${tw.muted}`}>
            <span className="font-medium text-ink/85">{profile.name}</span>
            <span className="text-ink/40"> · </span>
            <span className="tabular-nums">Updated {new Date(profile.lastUpdated).toLocaleString()}</span>
          </p>
          <div>
            <p className={`mb-2 ${fieldLabel}`}>Top categories</p>
            <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
              {profile.topCategories.map((slug) => (
                <li
                  key={slug}
                  className="rounded-pill border border-outline/50 bg-white/60 px-3 py-1.5 text-[0.75rem] font-medium text-ink/90"
                >
                  {formatCategorySlug(slug)}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className={`mb-3 ${fieldLabel}`}>Explicit preferences</p>
            <ul className={`${tw.chipList}`}>
              {profile.explicitPreferences.map((item) => (
                <li key={item.key} className={tw.chip}>
                  <span className="font-medium text-ink">{item.label}:</span> {item.value}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className={`${tw.labPanel} ${tw.labPanelPad} flex flex-col gap-5`}>
          <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Inferred interests</p>
          <h3 className={labelSerif}>From recent behaviour</h3>
          <ul className="m-0 grid list-none gap-4 p-0">
            {profile.inferredInterests.map((item) => (
              <li key={item.id} className="border-b border-outline/15 pb-4 last:border-b-0 last:pb-0">
                <p className="font-medium text-ink">{item.label}</p>
                <p className={`mt-1 text-sm leading-relaxed ${tw.muted}`}>{item.source}</p>
                <p className="mt-2 text-xs font-medium tabular-nums text-accent-strong">
                  {Math.round(item.confidence * 100)}% confidence
                </p>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className={`${tw.labPanel} ${tw.labPanelPad} flex flex-col gap-5`}>
          <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Why the app reacts</p>
          <h3 className={labelSerif}>Profile signals</h3>
          {explanationsLoading ? (
            <ul className="m-0 grid list-none gap-3 p-0" aria-busy>
              {[0, 1, 2].map((i) => (
                <li key={i} className="h-3.5 w-full max-w-lg animate-pulse rounded-md bg-ink/6" />
              ))}
            </ul>
          ) : explanationsError || !explanations ? (
            <p className={`text-sm leading-relaxed ${tw.muted}`}>
              Explainability strings could not be loaded. Explicit preferences and inferred rows above still reflect
              the latest profile snapshot.
            </p>
          ) : (
            <ul className="m-0 grid list-none gap-3.5 p-0">
              {explanations.profileSignals.map((item) => (
                <li key={item} className="flex gap-3 text-sm leading-relaxed tracking-body text-ink/88">
                  <span className="mt-[0.5em] h-1 w-1 shrink-0 rounded-full bg-accent/55" aria-hidden />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className={`${tw.labPanel} ${tw.labPanelPad} flex flex-col gap-4`}>
          <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Recent intent</p>
          <h3 className={labelSerif}>Session memory</h3>
          <ul className="m-0 grid list-none gap-2.5 p-0">
            {profile.recentSignals.map((line) => (
              <li
                key={line}
                className="border-l-2 border-accent/35 pl-3 text-sm leading-relaxed text-ink/85"
              >
                {line}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className={`${tw.labPanel} ${tw.labPanelPad} ${tw.stackMd}`}>
        <div className="flex flex-col gap-2 border-b border-outline/15 pb-5 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
          <div>
            <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Fit & sizing profile</p>
            <h3 className={`${tw.displayH2} mt-1 text-xl font-medium leading-snug sm:text-2xl`}>Planned surface</h3>
          </div>
          <span className="shrink-0 rounded-pill border border-dashed border-ink/35 bg-white/50 px-3 py-1 text-[0.65rem] font-semibold uppercase tracking-ui-wide text-ink/70">
            Not wired yet
          </span>
        </div>
        <p className={`text-sm leading-relaxed ${tw.muted}`}>
          Future builds will let shoppers save category-aware measurements (footwear, apparel, etc.). When{" "}
          <strong className="font-medium text-ink/90">personalization</strong> consent is on, HyperPersona may use those
          fields—together with browsing and purchase history—for search ranking, recommendations, and default variant or
          size. With personalization off, body or sizing inputs will not be described as driving the model (per FE_PLAN
          trust copy).
        </p>
        <fieldset disabled className="mt-2 grid gap-5 opacity-[0.72]">
          <legend className="sr-only">Fit and sizing — preview only</legend>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {(
              [
                { id: "g", label: "Gender presentation", ph: "e.g. Women’s / Men’s / Unisex" },
                { id: "h", label: "Height", ph: "e.g. 170 cm" },
                { id: "w", label: "Weight (optional)", ph: "—" },
                { id: "shoe", label: "Shoe size", ph: "US / EU ladder — planned" },
                { id: "waist", label: "Waist", ph: "Apparel ladder — planned" },
                { id: "chest", label: "Chest", ph: "Apparel ladder — planned" },
              ] as const
            ).map((f) => (
              <label key={f.id} className="grid gap-2">
                <span className={fieldLabel}>{f.label}</span>
                <input className={tw.fieldInput} placeholder={f.ph} defaultValue="" />
              </label>
            ))}
          </div>
          <p className={`text-xs leading-relaxed ${tw.muted}`}>
            Fields are non-interactive placeholders; saves will emit{" "}
            <code className="rounded bg-ink/6 px-1 py-0.5 text-[0.7rem]">profile_updated</code> and finer-grained fit
            events once the contract lands.
          </p>
        </fieldset>
      </section>
    </div>
  );
}

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { DemoPersona } from "@/features/personas/data";
import { usePersonaStore } from "@/features/personas/store";
import { Context } from "@/features/events/contexts";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import { apiClient } from "@/shared/api/client";
import type { RecommendResponse } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

type DemoScenario = {
  id: string;
  label: string;
  personaId: DemoPersona["id"];
  consentScopes: string[];
  note: string;
};

const scenarios: DemoScenario[] = [
  {
    id: "budget-generic",
    label: "Budget (generic)",
    personaId: "budget-shopper",
    consentScopes: ["analytics"],
    note: "Personalization off; rails should fall back to generic logic.",
  },
  {
    id: "premium-personalized",
    label: "Premium (personalized)",
    personaId: "premium-buyer",
    consentScopes: ["analytics", "personalization"],
    note: "Personalization on; confidence and reasons should read curated.",
  },
  {
    id: "gift-exploratory",
    label: "Gift (exploratory)",
    personaId: "gift-shopper",
    consentScopes: ["analytics", "personalization"],
    note: "Exploratory intent with weaker preference certainty.",
  },
];

type SnapshotShape = {
  reason: string;
  personalized: boolean;
  productNames: string[];
};

function toSnapshot(rail: RecommendResponse | undefined, generic: boolean): SnapshotShape | null {
  if (!rail) return null;
  return {
    reason: generic
      ? "Generic merchandising fallback (no personalization signal applied)."
      : rail.personalization_reason ?? "Personalized rail (no reason text returned).",
    personalized: !generic && Boolean(rail.personalization_reason),
    productNames: rail.products.slice(0, 3).map((p) => p.name),
  };
}

function RailSnapshot({ title, snapshot }: { title: string; snapshot: SnapshotShape | null }) {
  return (
    <section className="rounded-card border border-outline/25 bg-white/65 p-4 sm:p-5">
      <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>{title}</p>
      <ul className="m-0 mt-3 list-none space-y-2 p-0">
        {snapshot ? (
          <li className="rounded-md border border-outline/15 bg-white/60 px-3 py-2.5">
            <p className={`text-[0.78rem] leading-relaxed ${tw.muted}`}>{snapshot.reason}</p>
            <p className={`mt-1 text-[0.72rem] ${tw.muted}`}>
              {snapshot.personalized ? "Personalized" : "Generic fallback"}
            </p>
            <p className="mt-1 text-[0.75rem] text-ink/85">
              {snapshot.productNames.join(" · ") || "(no products)"}
            </p>
          </li>
        ) : (
          <li className={`rounded-md border border-outline/15 bg-white/60 px-3 py-2.5 text-[0.78rem] ${tw.muted}`}>
            Loading rail…
          </li>
        )}
      </ul>
    </section>
  );
}

function WalkthroughGuide() {
  return (
    <section className="rounded-card border border-outline/25 bg-white/65 p-4 sm:p-5">
      <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>How to read this page</p>
      <ol className="m-0 mt-3 list-decimal space-y-2.5 pl-4 text-sm leading-relaxed text-ink/88">
        <li>Select a scenario preset (Step 1).</li>
        <li>Compare left (generic) vs right (personalized) recommendation snapshots (Step 2).</li>
        <li>Advance fake checkout loop to show outcome signals feeding future recommendations (Step 3).</li>
      </ol>
    </section>
  );
}

function FakeOrderOutcomeLoop() {
  const track = useTrackEvent();
  const [step, setStep] = useState<0 | 1 | 2>(0);

  const labels = [
    "Cart intent captured",
    "Checkout simulated",
    "Next-session recommendations sharpened",
  ] as const;

  return (
    <section className="rounded-card border border-outline/25 bg-white/65 p-4 sm:p-5">
      <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>Fake order outcome loop</p>
      <ol className="m-0 mt-3 list-none space-y-2 p-0">
        {labels.map((label, idx) => {
          const active = idx <= step;
          return (
            <li
              key={label}
              className={`rounded-md border px-3 py-2 text-sm ${active ? "border-accent/45 bg-accent/8 text-ink/90" : "border-outline/15 bg-white/45 text-ink/70"}`}
            >
              {idx + 1}. {label}
            </li>
          );
        })}
      </ol>
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          className={tw.buttonEditorialBag}
          onClick={() => {
            const next = step === 2 ? 0 : ((step + 1) as 0 | 1 | 2);
            setStep(next);
            // Simulated demo-lab events — keep local-only namespace so they
            // don't pollute spec analytics; the real `purchase` event is
            // fired from `CheckoutForm` for genuine cart conversions.
            if (next === 1) {
              track({
                event_type: "demo_lab_checkout_started",
                payload: { source: "demo_lab" },
                consent_scope: ["analytics", "personalization"],
              });
            }
            if (next === 2) {
              track({
                event_type: "demo_lab_checkout_simulated",
                payload: { source: "demo_lab", simulated: true },
                consent_scope: ["analytics", "personalization"],
              });
            }
          }}
        >
          {step === 2 ? "Reset loop" : "Advance loop"}
        </button>
      </div>
      <p className={`mt-3 text-xs ${tw.muted}`} aria-live="polite">
        Current state: {labels[step]}.
      </p>
    </section>
  );
}

export function DemoLabPage() {
  const track = useTrackEvent();
  const queryClient = useQueryClient();
  const setPersona = usePersonaStore((state) => state.setPersona);
  const [activeScenarioId, setActiveScenarioId] = useState<string>(scenarios[0].id);

  const homepageContext = Context.homepage();
  const recommendationQuery = useQuery({
    queryKey: ["recommend", homepageContext],
    queryFn: () => apiClient.getRecommendation(homepageContext),
  });
  const consentQuery = useQuery({
    queryKey: ["consent"],
    queryFn: apiClient.getConsent,
  });

  const updateConsent = useMutation({
    mutationFn: (scopes: string[]) => apiClient.updateConsent(scopes),
    onSuccess: (next) => queryClient.setQueryData(["consent"], next),
  });

  const activeScenario = useMemo(
    () => scenarios.find((s) => s.id === activeScenarioId) ?? scenarios[0],
    [activeScenarioId],
  );

  const personalizedSnapshot = toSnapshot(recommendationQuery.data, false);
  const genericSnapshot = toSnapshot(recommendationQuery.data, true);
  const isPersonalized = Boolean(recommendationQuery.data?.personalization_reason);
  const personalizedCount = isPersonalized ? 1 : 0;
  const genericCount = recommendationQuery.data && !isPersonalized ? 1 : 0;

  return (
    <div className={`${tw.stackLg} min-h-[min(80vh,920px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
      <header className="max-w-3xl">
        <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Demo lab</p>
        <h1 className={`${tw.storyTitle} max-w-[24ch]`}>Scenario presets and comparison mode.</h1>
        <p className={`mt-4 max-w-2xl text-sm leading-relaxed ${tw.muted}`}>
          Phase 3 walkthrough surface. Use the numbered steps below to explain what changes, why it changes, and how
          outcome events sharpen the next recommendation cycle.
        </p>
      </header>

      <WalkthroughGuide />

      <section className={`${tw.labPanel} ${tw.labPanelPad}`}>
        <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>Step 1 · Scenario presets</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {scenarios.map((scenario) => (
            <button
              key={scenario.id}
              type="button"
              className={scenario.id === activeScenarioId ? tw.buttonEditorialBag : tw.buttonGhost}
              onClick={() => {
                setActiveScenarioId(scenario.id);
                setPersona(scenario.personaId);
                updateConsent.mutate(scenario.consentScopes);
                track({
                  event_type: "persona_switched",
                  payload: { personaId: scenario.personaId, preset: scenario.id },
                  consent_scope: ["analytics", "personalization"],
                });
              }}
            >
              {scenario.label}
            </button>
          ))}
        </div>
        <p className={`mt-3 text-sm ${tw.muted}`}>{activeScenario.note}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className={tw.chipInfo}>
            Consent: {(consentQuery.data?.scopes ?? []).join(", ") || "loading…"}
          </span>
          <span className={tw.chipSuccess}>
            Personalized rails: {personalizedCount}
          </span>
          <span className={tw.chipWarning}>
            Generic rails: {genericCount}
          </span>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center" aria-label="Step 2 comparison">
        <div className="grid gap-4 lg:grid-cols-2">
          <RailSnapshot title="Generic comparison snapshot" snapshot={genericSnapshot} />
          <RailSnapshot title="Personalized comparison snapshot" snapshot={personalizedSnapshot} />
        </div>
        <aside className="hidden lg:flex lg:flex-col lg:items-center lg:gap-3">
          <img
            src="/hero-product-cutout.webp"
            alt=""
            width={900}
            height={1272}
            loading="lazy"
            decoding="async"
            className="h-auto w-36 opacity-85 drop-shadow-[0_20px_42px_rgba(34,28,23,0.12)]"
          />
          <p className={`max-w-48 text-center text-xs leading-relaxed ${tw.muted}`}>
            Editorial packshot anchor for walkthrough framing.
          </p>
        </aside>
      </section>

      <p className={`-mt-2 text-xs ${tw.muted}`}>
        Step 2: compare reason text and confidence chips between the two cards above.
      </p>

      <FakeOrderOutcomeLoop />
      <p className={`-mt-2 text-xs ${tw.muted}`}>
        Step 3: run the loop to simulate conversion outcomes and explain future-rank feedback.
      </p>
    </div>
  );
}


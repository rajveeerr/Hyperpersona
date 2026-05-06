import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTrackEvent } from "@/features/events/useTrackEvent";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

const scopes = ["analytics", "personalization", "marketing"] as const;

const SCOPE_COPY: Record<(typeof scopes)[number], { title: string; description: string }> = {
  analytics: {
    title: "Analytics",
    description:
      "Product analytics, demo funnels, and the trace panel—so reviewers can see which events fired without turning on personalization.",
  },
  personalization: {
    title: "Personalization",
    description:
      "Search ranking, rails, default variant hints, and profile-driven tuning. When this is off, the storefront stays generic and we do not imply body or sizing fields influence results.",
  },
  marketing: {
    title: "Marketing",
    description:
      "Reserved for outbound or lifecycle messaging in a full rollout. In this demo it still toggles the consent record so scope changes stay auditable.",
  },
};

const pulse = "animate-pulse rounded-md bg-ink/6";

function ConsentSkeleton() {
  return (
    <div className={`${tw.stackLg}`} aria-busy aria-label="Loading consent">
      <div className="max-w-3xl space-y-3">
        <div className={`h-3 w-32 ${pulse}`} />
        <div className={`h-10 w-full max-w-lg ${pulse}`} />
        <div className={`h-4 w-full max-w-2xl ${pulse}`} />
      </div>
      <div className={`${tw.labPanel} ${tw.labPanelPad} space-y-4`}>
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center justify-between gap-4 border-b border-outline/12 py-3 last:border-0">
            <div className="grid flex-1 gap-2">
              <div className={`h-4 w-40 ${pulse}`} />
              <div className={`h-3 w-full max-w-md ${pulse}`} />
            </div>
            <div className={`h-8 w-14 rounded-pill ${pulse}`} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ConsentPage() {
  const queryClient = useQueryClient();
  const track = useTrackEvent();
  const consentQuery = useQuery({
    queryKey: ["consent"],
    queryFn: apiClient.getConsent,
  });
  const mutation = useMutation({
    mutationFn: (nextScopes: string[]) => apiClient.updateConsent(nextScopes),
    onSuccess: (next) => {
      queryClient.setQueryData(["consent"], next);
    },
  });

  if (consentQuery.isError) {
    return (
      <div className={`${tw.stackLg} min-h-[min(52vh,560px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
        <p className="text-sm text-red-800/90" role="alert">
          Could not load consent. Check your connection and try again.
        </p>
      </div>
    );
  }

  if (!consentQuery.data) {
    return (
      <div className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
        {consentQuery.isPending ? <ConsentSkeleton /> : null}
      </div>
    );
  }

  const selected = new Set(consentQuery.data.scopes);
  const personalizationOn = selected.has("personalization");
  const lastUpdated = new Date(consentQuery.data.lastUpdated).toLocaleString();

  return (
    <div className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
      <header className="max-w-3xl">
        <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Consent</p>
        <h1 className={`${tw.storyTitle} max-w-[24ch]`}>Trust controls that change what the demo can infer.</h1>
        <p className={`mt-4 max-w-2xl text-pretty text-sm leading-relaxed ${tw.muted}`}>
          Mirrors the floating consent toast behaviourally: turning personalization off should immediately read as a
          colder storefront—search, rails, and copy fall back to generic baselines (per FE_PLAN).
        </p>
      </header>

      <section className={`${tw.labPanel} ${tw.labPanelPad} max-w-2xl`}>
        <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Current record</p>
        <p className={`mt-1 text-sm ${tw.muted}`}>
          Last updated <span className="font-medium text-ink/88 tabular-nums">{lastUpdated}</span> · Customer{" "}
          <span className="font-mono text-xs text-ink/80">{consentQuery.data.customerId}</span>
        </p>
        <p className={`mt-4 text-sm leading-relaxed ${tw.muted}`}>
          {personalizationOn ? (
            <>
              <strong className="font-medium text-ink/90">Personalization is on.</strong> Search ranking, recommendations,
              and future fit or sizing fields (when shipped) may use consented profile and activity—not clickstream
              alone.
            </>
          ) : (
            <>
              <strong className="font-medium text-ink/90">Personalization is off.</strong> The UI should not imply that
              body, sizing, or inferred traits steer ranking until the shopper turns this scope back on.
            </>
          )}
        </p>
      </section>

      <section className={`${tw.labPanel} ${tw.labPanelPad} max-w-2xl`}>
        <div className="mb-6 flex flex-col gap-2 border-b border-outline/15 pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Scopes</p>
            <h2 className={`${tw.displayH2} mt-1 text-xl font-medium sm:text-2xl`}>What you allow</h2>
          </div>
          {mutation.isPending ? (
            <span className={`text-[0.7rem] font-medium uppercase tracking-ui-wide ${tw.muted}`}>Saving…</span>
          ) : null}
        </div>
        <ul className="m-0 grid list-none gap-0 p-0" role="list">
          {scopes.map((scope) => {
            const on = selected.has(scope);
            const copy = SCOPE_COPY[scope];
            return (
              <li
                key={scope}
                className="border-b border-outline/12 py-5 last:border-b-0"
              >
                <label
                  htmlFor={`consent-scope-${scope}`}
                  className="flex cursor-pointer flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-display text-[1.05rem] font-normal tracking-display text-ink">{copy.title}</p>
                    <p
                      id={`consent-scope-${scope}-desc`}
                      className={`mt-1 max-w-xl text-sm leading-relaxed ${tw.muted}`}
                    >
                      {copy.description}
                    </p>
                  </div>
                  <span className="flex shrink-0 items-center gap-3 self-start sm:self-center">
                    <span className={`text-[0.65rem] font-semibold uppercase tracking-ui-wide ${tw.muted}`}>
                      {on ? "On" : "Off"}
                    </span>
                    <input
                      id={`consent-scope-${scope}`}
                      type="checkbox"
                      className="size-5 shrink-0 rounded border border-outline accent-ink"
                      checked={on}
                      disabled={mutation.isPending}
                      aria-describedby={`consent-scope-${scope}-desc`}
                      onChange={() => {
                        const next = new Set(selected);
                        if (next.has(scope)) {
                          next.delete(scope);
                        } else {
                          next.add(scope);
                        }
                        const nextScopes = Array.from(next);
                        mutation.mutate(nextScopes);
                        track({
                          customer_id: "demo-customer-1",
                          event_type: "consent_updated",
                          payload: { scopes: nextScopes },
                          consent_scope: nextScopes,
                        });
                      }}
                    />
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        {mutation.isError ? (
          <p className="mt-4 text-sm text-red-800/90" role="alert">
            Consent could not be saved. Try again.
          </p>
        ) : null}
      </section>

      <section className={`${tw.labPanel} ${tw.labPanelPad} max-w-2xl opacity-[0.72]`}>
        <div className="flex flex-col gap-2 border-b border-outline/15 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Granular ad preferences</p>
          <span className="rounded-pill border border-dashed border-ink/35 bg-white/50 px-3 py-1 text-[0.65rem] font-semibold uppercase tracking-ui-wide text-ink/65">
            Planned
          </span>
        </div>
        <p className={`text-sm leading-relaxed ${tw.muted}`}>
          Future work may split marketing into channel-level toggles (email, paid social, on-site). Until the contract
          extends, only the coarse <strong className="font-medium text-ink/85">marketing</strong> scope above is
          writable—this block stays read-only so reviewers know what is still out of scope.
        </p>
      </section>
    </div>
  );
}

import { useMemo, useState } from "react";

import { useAuth } from "@/features/auth/useAuth";
import { useConsentMutation, useConsentQuery } from "@/features/consent/useConsent";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import {
  CONSENT_RETENTION_OPTIONS,
  CONSENT_SCOPES,
  type ConsentScope,
} from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

const SCOPE_COPY: Record<ConsentScope, { title: string; description: string }> = {
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

/** Recommended scopes when a brand-new user first lands on this page. */
const DEFAULT_SCOPES: ConsentScope[] = ["analytics", "personalization"];
const DEFAULT_RETENTION = 90;

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

const Header = () => (
  <header className="max-w-3xl">
    <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Consent</p>
    <h1 className={`${tw.storyTitle} max-w-[24ch]`}>Trust controls that change what the demo can infer.</h1>
    <p className={`mt-4 max-w-2xl text-pretty text-sm leading-relaxed ${tw.muted}`}>
      Mirrors the floating consent toast behaviourally: turning personalization off should immediately read as a colder
      storefront—search, rails, and copy fall back to generic baselines (per FE_PLAN).
    </p>
  </header>
);

export function ConsentPage() {
  const { customerId } = useAuth();
  const track = useTrackEvent();
  const consent = useConsentQuery();
  const mutation = useConsentMutation();

  if (consent.isFatalError) {
    return (
      <div className={`${tw.stackLg} min-h-[min(52vh,560px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
        <Header />
        <p className="text-sm text-red-800/90" role="alert">
          Could not load consent. Check your connection and try again.
        </p>
      </div>
    );
  }

  if (consent.isPending) {
    return (
      <div className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
        <Header />
        <ConsentSkeleton />
      </div>
    );
  }

  if (consent.isMissing || !consent.record) {
    return (
      <ConsentSetup
        customerId={customerId}
        busy={mutation.isPending}
        error={mutation.isError ? "Consent could not be saved. Try again." : null}
        onSubmit={(scopes, retention) => {
          mutation.mutate({ scopes, data_retention_days: retention });
          track({
            customer_id: customerId ?? "demo-customer-1",
            event_type: "consent_updated",
            payload: { scopes, data_retention_days: retention, action: "create" },
            consent_scope: scopes,
          });
        }}
      />
    );
  }

  return (
    <ConsentEditor
      record={consent.record}
      busy={mutation.isPending}
      error={mutation.isError ? "Consent could not be saved. Try again." : null}
      onChangeScopes={(nextScopes) => {
        mutation.mutate({
          scopes: nextScopes,
          data_retention_days: consent.record!.data_retention_days,
        });
        track({
          customer_id: customerId ?? "demo-customer-1",
          event_type: "consent_updated",
          payload: { scopes: nextScopes, data_retention_days: consent.record!.data_retention_days },
          consent_scope: nextScopes,
        });
      }}
      onChangeRetention={(retention) => {
        mutation.mutate({ scopes: consent.record!.scopes, data_retention_days: retention });
        track({
          customer_id: customerId ?? "demo-customer-1",
          event_type: "consent_updated",
          payload: { scopes: consent.record!.scopes, data_retention_days: retention },
          consent_scope: consent.record!.scopes,
        });
      }}
    />
  );
}

// -----------------------------------------------------------------------------
// First-time setup — POST creates the consent record server-side.

type SetupProps = {
  customerId: string | null;
  busy: boolean;
  error: string | null;
  onSubmit: (scopes: string[], retention: number) => void;
};

function ConsentSetup({ customerId, busy, error, onSubmit }: SetupProps) {
  const [scopes, setScopes] = useState<Set<ConsentScope>>(() => new Set(DEFAULT_SCOPES));
  const [retention, setRetention] = useState<number>(DEFAULT_RETENTION);

  const orderedScopes = useMemo(() => CONSENT_SCOPES.filter((scope) => scopes.has(scope)), [scopes]);

  return (
    <div className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
      <Header />

      <section className={`${tw.labPanel} ${tw.labPanelPad} max-w-2xl`}>
        <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Set up your record</p>
        <h2 className={`${tw.displayH2} mt-1 text-xl font-medium sm:text-2xl`}>No consent record yet</h2>
        <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
          Pick the scopes you want to allow and how long the demo may keep behavioral data. You can change either at
          any time. Customer{" "}
          <span className="font-mono text-xs text-ink/80">{customerId ?? "—"}</span>.
        </p>

        <ScopeRows
          selected={scopes}
          disabled={busy}
          onToggle={(scope) => {
            setScopes((prev) => {
              const next = new Set(prev);
              if (next.has(scope)) next.delete(scope);
              else next.add(scope);
              return next;
            });
          }}
        />

        <RetentionPicker
          value={retention}
          disabled={busy}
          onChange={setRetention}
        />

        {error ? (
          <p className="mt-4 text-sm text-red-800/90" role="alert">{error}</p>
        ) : null}

        <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-outline/15 pt-6">
          <button
            type="button"
            className={tw.buttonEditorialBag}
            disabled={busy}
            onClick={() => onSubmit(orderedScopes, retention)}
          >
            {busy ? "Saving…" : "Save consent"}
          </button>
          <span className={`text-xs ${tw.muted}`}>You'll be able to revoke or change these any time.</span>
        </div>
      </section>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Editing an existing record.

type EditorProps = {
  record: NonNullable<ReturnType<typeof useConsentQuery>["record"]>;
  busy: boolean;
  error: string | null;
  onChangeScopes: (scopes: string[]) => void;
  onChangeRetention: (retention: number) => void;
};

function ConsentEditor({ record, busy, error, onChangeScopes, onChangeRetention }: EditorProps) {
  const selected = useMemo(() => new Set(record.scopes as ConsentScope[]), [record.scopes]);
  const personalizationOn = selected.has("personalization");
  const lastUpdated = record.last_updated ? new Date(record.last_updated).toLocaleString() : "—";

  return (
    <div className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
      <Header />

      <section className={`${tw.labPanel} ${tw.labPanelPad} max-w-2xl`}>
        <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Current record</p>
        <p className={`mt-1 text-sm ${tw.muted}`}>
          Last updated <span className="font-medium text-ink/88 tabular-nums">{lastUpdated}</span> · Customer{" "}
          <span className="font-mono text-xs text-ink/80">{record.customer_id}</span>
        </p>
        <p className={`mt-4 text-sm leading-relaxed ${tw.muted}`}>
          {personalizationOn ? (
            <>
              <strong className="font-medium text-ink/90">Personalization is on.</strong> Search ranking, recommendations,
              and future fit or sizing fields (when shipped) may use consented profile and activity—not clickstream alone.
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
          {busy ? (
            <span className={`text-[0.7rem] font-medium uppercase tracking-ui-wide ${tw.muted}`}>Saving…</span>
          ) : null}
        </div>

        <ScopeRows
          selected={selected}
          disabled={busy}
          onToggle={(scope) => {
            const next = new Set(selected);
            if (next.has(scope)) next.delete(scope);
            else next.add(scope);
            onChangeScopes(CONSENT_SCOPES.filter((s) => next.has(s)));
          }}
        />

        {error ? (
          <p className="mt-4 text-sm text-red-800/90" role="alert">{error}</p>
        ) : null}
      </section>

      <section className={`${tw.labPanel} ${tw.labPanelPad} max-w-2xl`}>
        <div className="mb-6 border-b border-outline/15 pb-6">
          <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Data retention</p>
          <h2 className={`${tw.displayH2} mt-1 text-xl font-medium sm:text-2xl`}>How long we may keep behavioral data</h2>
          <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
            The server uses this as the TTL on every event row. Lower = stricter; higher = more recall for ranking.
          </p>
        </div>

        <RetentionPicker
          value={record.data_retention_days}
          disabled={busy}
          onChange={onChangeRetention}
        />
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

// -----------------------------------------------------------------------------
// Reusable scope + retention controls.

type ScopeRowsProps = {
  selected: Set<ConsentScope>;
  disabled: boolean;
  onToggle: (scope: ConsentScope) => void;
};

function ScopeRows({ selected, disabled, onToggle }: ScopeRowsProps) {
  return (
    <ul className="m-0 grid list-none gap-0 p-0" role="list">
      {CONSENT_SCOPES.map((scope) => {
        const on = selected.has(scope);
        const copy = SCOPE_COPY[scope];
        return (
          <li key={scope} className="border-b border-outline/12 py-5 last:border-b-0">
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
                  disabled={disabled}
                  aria-describedby={`consent-scope-${scope}-desc`}
                  onChange={() => onToggle(scope)}
                />
              </span>
            </label>
          </li>
        );
      })}
    </ul>
  );
}

type RetentionPickerProps = {
  value: number;
  disabled: boolean;
  onChange: (retention: number) => void;
};

function RetentionPicker({ value, disabled, onChange }: RetentionPickerProps) {
  return (
    <div
      className="mt-6 flex flex-wrap gap-2"
      role="radiogroup"
      aria-label="Data retention window in days"
    >
      {CONSENT_RETENTION_OPTIONS.map((option) => {
        const active = option === value;
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            onClick={() => onChange(option)}
            className={
              active
                ? "min-h-10 cursor-pointer rounded-pill border border-ink/30 bg-surface-strong px-4 py-2 text-[0.75rem] font-semibold tabular-nums text-ink shadow-[0_6px_18px_rgba(34,28,23,0.06)] ring-1 ring-inset ring-white/65 transition-colors disabled:opacity-55"
                : "min-h-10 cursor-pointer rounded-pill border border-dashed border-ink/40 bg-white/70 px-4 py-2 text-[0.75rem] font-medium tabular-nums text-ink transition-colors hover:border-ink/55 hover:bg-white disabled:opacity-55"
            }
          >
            {option} days
          </button>
        );
      })}
    </div>
  );
}

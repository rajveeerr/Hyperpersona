import { FormEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";
import { ApiError } from "@/shared/api/contracts";
import type { TraceRow } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

const eyebrow = `text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`;
const mono = "font-mono tabular-nums tracking-body";
const codeBlock =
  "rounded-[max(var(--radius-inner),1rem)] border border-outline/35 bg-ink/[0.035] px-5 py-4 pr-20 sm:px-6 sm:py-5 sm:pr-24 overflow-x-auto font-mono text-[0.78rem] leading-relaxed text-ink/90 whitespace-pre-wrap break-words tracking-body";

function CopyIcon({ copied }: { copied: boolean }) {
  if (copied) {
    return (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <polyline points="20 6 9 17 4 12" />
      </svg>
    );
  }
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function CopyButton({
  text,
  label = "Copy",
  className,
}: {
  text: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  const base =
    "inline-flex cursor-pointer items-center gap-1.5 rounded-pill border border-outline/45 bg-surface-strong/85 px-2.5 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-ink shadow-[0_4px_12px_rgba(34,28,23,0.06)] backdrop-blur-[6px] transition-[transform,background-color,border-color,opacity] duration-150 hover:-translate-y-px hover:border-ink/40 hover:bg-surface-strong focus-visible:-translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1800);
        } catch {
          // clipboard unavailable; no-op
        }
      }}
      aria-label={copied ? "Copied to clipboard" : `Copy ${label.toLowerCase()} to clipboard`}
      aria-live="polite"
      className={`${base}${className ? ` ${className}` : ""}`}
    >
      <CopyIcon copied={copied} />
      <span>{copied ? "Copied" : label}</span>
    </button>
  );
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  const isEmpty = value === null || value === undefined;
  const text = isEmpty ? "" : JSON.stringify(value, null, 2);
  return (
    <div className="space-y-2">
      <p className={`${eyebrow} text-ink`}>{label}</p>
      {isEmpty ? (
        <p className={`text-sm italic ${tw.muted}`}>None</p>
      ) : (
        <div className="relative">
          <pre className={codeBlock}>
            <code>{text}</code>
          </pre>
          <CopyButton text={text} label={label} className="absolute right-3 top-3" />
        </div>
      )}
    </div>
  );
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return "—";
  if (ms === 0) return "—";
  if (ms < 1) return `${(ms * 1000).toFixed(0)} µs`;
  if (ms < 1000) return `${ms.toFixed(ms < 10 ? 1 : 0)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function formatOffset(seconds: number): string {
  if (seconds === 0) return "+0.00s";
  return `+${seconds.toFixed(2)}s`;
}

/** Friendly label per (agent_name, step), falling back to the raw step. */
function describeStep(row: TraceRow): string {
  const key = `${row.agent_name}/${row.step}`;
  switch (key) {
    case "supervisor/start":
    case "supervisor/start_recommend":
    case "supervisor/start_complement":
      return "Pipeline start";
    case "supervisor/end":
    case "supervisor/end_recommend":
    case "supervisor/end_complement":
      return "Pipeline end";
    case "supervisor/blocked":
      return "Blocked (consent or privacy)";
    case "privacy/check_privacy":
      return "Privacy check";
    case "analyzer/analyze_behavior":
      return "Behavioral analysis";
    case "router/cheap_store":
      return "Low-signal event batched";
    case "summarizer/session_summary":
      return "Session summary";
    case "summarizer/noop":
      return "Summarizer (no work)";
    case "recommender/generate_recommendation":
      return "Recommendation generation";
    case "verifier/verify_recommendation":
      return "Recommendation verification";
    case "products_picker/pick_products":
      return "Product selection";
    case "complement/facts_retrieved":
      return "Complement facts retrieved";
    case "complement/generate_complement":
      return "Complement generation";
    case "agentcore/invoke_agent_runtime":
      return "AgentCore invocation";
    case "model/model_call":
      return "Model call";
    default:
      return row.step;
  }
}

type DerivedRow = {
  row: TraceRow;
  offsetMs: number;
  durationMs: number;
  isMarker: boolean;
};

type Derived = {
  rows: DerivedRow[];
  startedAtMs: number;
  endedAtMs: number;
  totalMs: number;
  agentCount: number;
  errorCount: number;
};

function deriveTimeline(rows: TraceRow[]): Derived {
  const sorted = [...rows].sort((a, b) => {
    const ta = Date.parse(a.timestamp);
    const tb = Date.parse(b.timestamp);
    if (ta !== tb) return ta - tb;
    return a.id - b.id;
  });
  const startedAtMs = sorted.length > 0 ? Date.parse(sorted[0].timestamp) : 0;
  let endedAtMs = startedAtMs;
  const agents = new Set<string>();
  let errorCount = 0;

  const derived: DerivedRow[] = sorted.map((row) => {
    const ts = Date.parse(row.timestamp);
    const dur = row.duration_ms ?? 0;
    const isMarker = dur === 0;
    const eventEnd = ts + dur;
    if (eventEnd > endedAtMs) endedAtMs = eventEnd;
    agents.add(row.agent_name);
    if (row.status !== "ok") errorCount += 1;
    return {
      row,
      offsetMs: ts - startedAtMs,
      durationMs: dur,
      isMarker,
    };
  });

  return {
    rows: derived,
    startedAtMs,
    endedAtMs,
    totalMs: endedAtMs - startedAtMs,
    agentCount: agents.size,
    errorCount,
  };
}

function PageHero() {
  return (
    <header className="max-w-3xl">
      <p className={`mb-2 ${eyebrow}`}>Agent Traces</p>
      <h1 className={`${tw.storyTitle} max-w-[24ch]`}>
        See what the agents did, step by step.
      </h1>
      <p className={`mt-5 max-w-2xl text-pretty text-sm leading-relaxed ${tw.muted}`}>
        Every recommendation, event, and complement run is logged span by span —
        which agent ran, what it received, what it returned, how long it took.
        Paste a job id to inspect the run.
      </p>
    </header>
  );
}

function JobIdForm({
  initialValue,
  onSubmit,
}: {
  initialValue: string;
  onSubmit: (jobId: string) => void;
}) {
  const [value, setValue] = useState(initialValue);
  const handle = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
  };
  return (
    <form onSubmit={handle} className={`${tw.labPanel} ${tw.labPanelPad} flex flex-col gap-4 sm:flex-row sm:items-end`}>
      <label className="flex-1 space-y-2">
        <span className={`${eyebrow} text-ink`}>Job ID</span>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="e.g. evt_6ce70085-3304-459e-96a3-2bdef8025b4a"
          className={`${tw.fieldInput} w-full font-mono text-sm`}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
        />
      </label>
      <button type="submit" className={`${tw.button} ${tw.buttonCommerce}`} disabled={!value.trim()}>
        Load trace
      </button>
    </form>
  );
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>{label}</dt>
      <dd className={`${mono} text-sm font-medium text-ink`}>{value}</dd>
    </div>
  );
}

function JobSummary({ jobId, derived }: { jobId: string; derived: Derived }) {
  const startedDate = new Date(derived.startedAtMs);
  const errorChip = derived.errorCount > 0 ? tw.chipError : tw.chipSuccess;
  const errorLabel = derived.errorCount > 0 ? `${derived.errorCount} error${derived.errorCount > 1 ? "s" : ""}` : "All ok";
  return (
    <section className={`${tw.labPanel} ${tw.labPanelPad} space-y-5`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-2">
          <p className={eyebrow}>Job</p>
          <div className="flex flex-wrap items-center gap-2">
            <code className={`${mono} max-w-full truncate rounded-md bg-ink/[0.06] px-2 py-1 text-[0.78rem] text-ink`}>
              {jobId}
            </code>
            <CopyButton text={jobId} label="ID" />
          </div>
        </div>
        <span className={errorChip}>{errorLabel}</span>
      </div>
      <dl className="grid grid-cols-2 gap-y-4 gap-x-8 sm:grid-cols-4">
        <StatPill label="Spans" value={String(derived.rows.length)} />
        <StatPill label="Agents" value={String(derived.agentCount)} />
        <StatPill label="Total time" value={formatDuration(derived.totalMs)} />
        <StatPill label="Started" value={startedDate.toLocaleTimeString()} />
      </dl>
    </section>
  );
}

function SpanRow({
  derivedRow,
  totalMs,
  expanded,
  onToggle,
}: {
  derivedRow: DerivedRow;
  totalMs: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { row, offsetMs, durationMs, isMarker } = derivedRow;
  const offsetPct = totalMs > 0 ? Math.min(100, (offsetMs / totalMs) * 100) : 0;
  const rawWidthPct = totalMs > 0 ? (durationMs / totalMs) * 100 : 0;
  const widthPct = isMarker ? 0 : Math.max(1.5, Math.min(100 - offsetPct, rawWidthPct));
  const ok = row.status === "ok";
  const barColor = ok ? "bg-success/70" : "bg-error/70";
  const trackColor = "bg-outline/15";

  return (
    <li className={`${tw.labPanel} px-5 py-4 sm:px-6 sm:py-5`}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="group flex w-full cursor-pointer flex-col gap-3 text-left"
      >
        <div className="grid grid-cols-[64px_minmax(0,1fr)_minmax(0,2fr)_72px] items-center gap-4 sm:grid-cols-[80px_minmax(0,1fr)_minmax(0,2.4fr)_88px] sm:gap-5">
          <span className={`${mono} text-[0.7rem] ${tw.muted}`}>{formatOffset(offsetMs / 1000)}</span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium tracking-body text-ink">{describeStep(row)}</p>
            <p className={`truncate text-xs ${tw.muted}`}>
              <span className={mono}>{row.agent_name}</span>
              <span className="px-1.5 opacity-50">·</span>
              <span className={mono}>{row.step}</span>
            </p>
          </div>
          <div className="relative h-2 overflow-visible rounded-full">
            <div className={`absolute inset-y-0 left-0 right-0 rounded-full ${trackColor}`} aria-hidden />
            {isMarker ? (
              <span
                aria-hidden
                className={`absolute top-1/2 -translate-y-1/2 h-3 w-[3px] rounded-sm ${ok ? "bg-ink/55" : "bg-error"}`}
                style={{ left: `${offsetPct}%` }}
              />
            ) : (
              <div
                aria-hidden
                className={`absolute inset-y-0 rounded-full ${barColor}`}
                style={{ left: `${offsetPct}%`, width: `${widthPct}%` }}
              />
            )}
          </div>
          <div className="flex items-center justify-end gap-2">
            <span className={`${mono} text-[0.78rem] text-ink`}>{formatDuration(durationMs)}</span>
            <span
              aria-hidden
              className={`text-xs leading-none ${tw.muted} transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
            >
              ›
            </span>
          </div>
        </div>
      </button>
      {expanded ? (
        <div className="mt-5 border-t border-outline/25 pt-5">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <span className={ok ? tw.chipSuccess : tw.chipError}>{row.status}</span>
            <span className={`text-xs ${tw.muted}`}>
              <span className={mono}>{row.timestamp}</span>
            </span>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <JsonBlock label="Input" value={row.input} />
            <JsonBlock label="Output" value={row.output} />
          </div>
        </div>
      ) : null}
    </li>
  );
}

function TraceTimeline({ derived }: { derived: Derived }) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const allOpen = derived.rows.length > 0 && derived.rows.every(({ row }) => expanded[row.id]);
  return (
    <section className="space-y-4">
      <div className={tw.flexBetween}>
        <div>
          <p className={eyebrow}>Spans</p>
          <h2 className={`${tw.displayH2} mt-2 text-[clamp(1.4rem,2.4vw,2rem)]`}>Timeline</h2>
        </div>
        <button
          type="button"
          className={`${tw.buttonGhost} ${tw.buttonSmall}`}
          onClick={() => {
            if (allOpen) {
              setExpanded({});
            } else {
              const next: Record<number, boolean> = {};
              derived.rows.forEach(({ row }) => {
                next[row.id] = true;
              });
              setExpanded(next);
            }
          }}
        >
          {allOpen ? "Collapse all" : "Expand all"}
        </button>
      </div>
      <ul role="list" className="m-0 grid list-none gap-3 p-0">
        {derived.rows.map((dr) => (
          <SpanRow
            key={dr.row.id}
            derivedRow={dr}
            totalMs={derived.totalMs}
            expanded={!!expanded[dr.row.id]}
            onToggle={() =>
              setExpanded((prev) => ({ ...prev, [dr.row.id]: !prev[dr.row.id] }))
            }
          />
        ))}
      </ul>
    </section>
  );
}

function LoadingState() {
  return (
    <section className={`${tw.labPanel} ${tw.labPanelPad} space-y-3`} aria-busy="true">
      <div className="h-4 w-1/3 animate-pulse rounded bg-outline/30" />
      <div className="grid gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded-2xl bg-outline/20" />
        ))}
      </div>
    </section>
  );
}

function ErrorState({ error, jobId }: { error: unknown; jobId: string }) {
  let title = "Could not load traces";
  let body = "Unexpected error while fetching the trace.";
  if (error instanceof ApiError) {
    if (error.status === 404) {
      title = "No traces for that job";
      body = `Either the job hasn't completed yet, the id (${jobId}) is wrong, or the trace hasn't synced from the worker. S3 lookup covers the last 7 days.`;
    } else if (error.status === 503) {
      title = "Trace storage unavailable";
      body = "The server has no local trace files and S3 sync is not configured. Set TRACE_SYNC_MODE=s3 with S3_TRACES_BUCKET and try again.";
    } else if (error.status === 401) {
      title = "Sign in required";
      body = "Trace access needs a logged-in session.";
    } else {
      body = error.message || body;
    }
  } else if (error instanceof Error) {
    body = error.message;
  }
  return (
    <section className={`${tw.labPanel} ${tw.labPanelPad} space-y-2`}>
      <p className={eyebrow}>Error</p>
      <h2 className={`${tw.displayH2} text-[1.35rem]`}>{title}</h2>
      <p className={`text-sm leading-relaxed ${tw.muted}`}>{body}</p>
    </section>
  );
}

function EmptyState() {
  return (
    <section className={`${tw.labPanel} ${tw.labPanelPad} space-y-2`}>
      <p className={eyebrow}>Try it</p>
      <h2 className={`${tw.displayH2} text-[1.35rem]`}>Paste a job id above</h2>
      <p className={`text-sm leading-relaxed ${tw.muted}`}>
        Recommend jobs come back in the <code className="font-mono text-ink">job_id</code>{" "}
        field of <code className="font-mono text-ink">/recommend</code>; event jobs in the{" "}
        <code className="font-mono text-ink">job_id</code> of each item in{" "}
        <code className="font-mono text-ink">/events/batch</code>.
      </p>
    </section>
  );
}

export function TracesPage() {
  const [jobId, setJobId] = useState<string | null>(null);

  const query = useQuery<TraceRow[]>({
    queryKey: ["traces", jobId],
    queryFn: () => apiClient.getTraces(jobId!),
    enabled: !!jobId,
    retry: 0,
    staleTime: 0,
  });

  const derived = useMemo(
    () => (query.data && query.data.length > 0 ? deriveTimeline(query.data) : null),
    [query.data],
  );

  return (
    <div
      className={`${tw.stackLg} min-h-[min(76vh,880px)] gap-12 pt-8 pb-12 sm:gap-14 sm:pt-10 sm:pb-14 lg:gap-16 lg:pt-12 lg:pb-16`}
    >
      <PageHero />
      <JobIdForm initialValue={jobId ?? ""} onSubmit={setJobId} />
      {!jobId ? <EmptyState /> : null}
      {jobId && query.isPending ? <LoadingState /> : null}
      {jobId && query.isError ? <ErrorState error={query.error} jobId={jobId} /> : null}
      {jobId && derived ? (
        <>
          <JobSummary jobId={jobId} derived={derived} />
          <TraceTimeline derived={derived} />
        </>
      ) : null}
    </div>
  );
}

import { useCallback, useEffect, useId, useState } from "react";

import { useDebugEventStore } from "@/features/events/debug/store";
import { env } from "@/shared/config/env";
import { tw } from "@/shared/ui/tw";

const STORAGE_KEY = "hyperpersona-debug-panel-open";

function Chevron({ up, className }: { up: boolean; className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d={up ? "M4 10l4-4 4 4" : "M12 6L8 10 4 6"}
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function DebugEventPanel() {
  const panelId = useId();
  const localEvents = useDebugEventStore((state) => state.events);
  const [open, setOpen] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.sessionStorage.getItem(STORAGE_KEY) === "1";
  });

  const setOpenPersisted = useCallback((next: boolean) => {
    setOpen(next);
  }, []);

  useEffect(() => {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, open ? "1" : "0");
    } catch {
      /* noop */
    }
  }, [open]);

  if (!env.debugPanelEnabled) {
    return null;
  }

  const shell =
    "border border-outline/35 bg-[radial-gradient(ellipse_92%_88%_at_50%_0%,#fffefb_0%,#faf7f2_55%,#f0ebe3_100%)] shadow-[0_28px_80px_rgba(62,40,27,0.08)] backdrop-blur-md";

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-60 flex w-[min(380px,calc(100vw-1.5rem))] flex-col items-end gap-2 sm:bottom-5 sm:right-5">
      {open ? (
        <aside
          id={panelId}
          className={`pointer-events-auto w-full max-h-[min(52vh,420px)] rounded-[1.2rem] ${shell} p-4 sm:p-5`}
          aria-label="Frontend event trace"
        >
          <div className="flex items-start justify-between gap-3 border-b border-outline/15 pb-3">
            <div className="min-w-0">
              <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>Trace</p>
              <h3 className={`${tw.displayH2} mt-1 text-lg leading-tight sm:text-xl`}>Event stream</h3>
              <p className={`mt-1 text-[0.75rem] leading-snug ${tw.muted}`}>Local tracking log for this session.</p>
            </div>
            <button
              type="button"
              className="inline-flex size-9 shrink-0 items-center justify-center rounded-full border border-outline/50 bg-white/50 text-ink/80 transition-colors hover:border-ink/25 hover:bg-white/80"
              onClick={() => setOpenPersisted(false)}
              aria-expanded={true}
              aria-controls={panelId}
              aria-label="Collapse event trace"
            >
              <Chevron up={false} className="opacity-80" />
            </button>
          </div>
          <div className="mt-3 grid max-h-[min(38vh,300px)] gap-0 overflow-auto pr-1">
            {localEvents.length === 0 ? (
              <p className={`py-6 text-center text-sm ${tw.muted}`}>Interact with the storefront to populate events.</p>
            ) : (
              localEvents.map((event) => (
                <article
                  key={event.event_id}
                  className="border-b border-outline/10 py-2.5 last:border-b-0"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-mono text-[0.7rem] font-medium uppercase tracking-wide text-ink/90">
                      {event.event_type}
                    </span>
                    <time className={`shrink-0 tabular-nums text-[0.65rem] ${tw.muted}`}>
                      {new Date(event.created_at).toLocaleTimeString(undefined, {
                        hour: "numeric",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </time>
                  </div>
                </article>
              ))
            )}
          </div>
        </aside>
      ) : null}

      <button
        type="button"
        className={`pointer-events-auto inline-flex items-center gap-2 rounded-pill border border-outline/45 bg-white/55 px-4 py-2.5 text-ink shadow-[0_12px_40px_rgba(34,28,23,0.08)] backdrop-blur-md transition-[transform,box-shadow,border-color] duration-150 hover:border-ink/20 hover:shadow-[0_16px_48px_rgba(34,28,23,0.1)] active:scale-[0.99] sm:px-5`}
        onClick={() => setOpenPersisted(!open)}
        aria-expanded={open}
        {...(open ? { "aria-controls": panelId } : {})}
        aria-label={open ? "Collapse event trace" : "Open event trace"}
      >
        <span className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>Trace</span>
        <span className="text-[0.8125rem] font-medium tracking-[0.02em]">Events</span>
        {localEvents.length > 0 ? (
          <span className="rounded-pill border border-outline/40 bg-ink/[0.06] px-2 py-0.5 font-mono text-[0.65rem] tabular-nums text-ink/80">
            {localEvents.length}
          </span>
        ) : null}
        <Chevron up={!open} className="text-ink/55" />
      </button>
    </div>
  );
}

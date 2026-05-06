import { useEffect, useReducer, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useTrackEvent } from "@/features/events/useTrackEvent";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

const SESSION_DISMISS_PREFIX = "hyperpersona-consent-banner-dismissed";

function dismissStorageKey(personalizationOn: boolean) {
  return `${SESSION_DISMISS_PREFIX}:${personalizationOn ? "on" : "off"}`;
}

function readDismissed(personalizationOn: boolean) {
  if (typeof window === "undefined") return false;
  try {
    return window.sessionStorage.getItem(dismissStorageKey(personalizationOn)) === "1";
  } catch {
    return false;
  }
}

/**
 * Viewport anchor only — **no transform** on this node (Safari quirk: `transform` on `fixed` breaks viewport pinning).
 * Exit motion lives on an inner `motion.div`.
 */
const toastAnchor =
  "pointer-events-none fixed top-[8.875rem] z-40 w-[min(100%,22rem)] max-w-md md:top-[5.85rem] end-3 sm:end-5";

const pop =
  "relative isolate w-full rounded-[1.15rem] border border-outline/20 bg-white/72 px-4 py-3 pr-11 shadow-[0_10px_36px_rgba(62,40,27,0.045)] backdrop-blur-sm sm:px-4 sm:py-3.5 sm:pr-12";

function DismissNoticeButton({ onDismiss }: { onDismiss: () => void }) {
  return (
    <button
      type="button"
      onClick={onDismiss}
      className="absolute right-2.5 top-2.5 inline-flex size-8 items-center justify-center rounded-md text-ink/45 transition-colors hover:bg-ink/6 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      aria-label="Dismiss personalization notice for this session"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
      </svg>
    </button>
  );
}

type NudgePanelProps = {
  personalizationOn: boolean;
  onExitComplete: () => void;
  children: (requestClose: () => void) => React.ReactNode;
};

function ConsentNudgePanel({ personalizationOn, onExitComplete, children }: NudgePanelProps) {
  const reduceMotion = useReducedMotion();
  const [open, setOpen] = useState(true);

  useEffect(() => {
    setOpen(true);
  }, [personalizationOn]);

  const handleDismiss = () => {
    setOpen(false);
  };

  return (
    <div className={toastAnchor}>
      <AnimatePresence onExitComplete={onExitComplete}>
        {open ? (
          <motion.div
            key={personalizationOn ? "nudge-on" : "nudge-off"}
            className="pointer-events-auto w-full"
            role="status"
            aria-live="polite"
            initial={false}
            exit={
              reduceMotion
                ? { opacity: 0 }
                : { opacity: 0, x: 56, scale: 0.97 }
            }
            transition={
              reduceMotion
                ? { duration: 0.16, ease: [0.22, 1, 0.36, 1] }
                : { type: "spring", stiffness: 420, damping: 30, mass: 0.72 }
            }
          >
            {children(handleDismiss)}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export function ConsentBanner() {
  const queryClient = useQueryClient();
  const track = useTrackEvent();
  const [, forceRerender] = useReducer((c: number) => c + 1, 0);
  const consentQuery = useQuery({
    queryKey: ["consent"],
    queryFn: apiClient.getConsent,
  });

  const persistDismiss = (personalizationOn: boolean) => {
    try {
      window.sessionStorage.setItem(dismissStorageKey(personalizationOn), "1");
    } catch {
      /* private mode / quota */
    }
    forceRerender();
  };

  const updateConsent = useMutation({
    mutationFn: (scopes: string[]) => apiClient.updateConsent(scopes),
    onSuccess: (next) => {
      queryClient.setQueryData(["consent"], next);
    },
  });

  if (!consentQuery.data) {
    return null;
  }

  const hasPersonalization = consentQuery.data.scopes.includes("personalization");
  if (readDismissed(hasPersonalization)) {
    return null;
  }

  if (hasPersonalization) {
    return (
      <ConsentNudgePanel personalizationOn onExitComplete={() => persistDismiss(true)}>
        {(requestClose) => (
          <div className={`${pop} ring-1 ring-success/12`}>
            <DismissNoticeButton onDismiss={requestClose} />
            <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
              <span className="text-pretty text-[0.8125rem] font-medium leading-relaxed tracking-body text-ink/88">
                Personalization is on ranking and search may use consented activity.
              </span>
              <Link
                to="/consent"
                className={`${tw.buttonGhost} ${tw.buttonSmall} shrink-0 self-start border-ink/20 sm:self-auto`}
              >
                Review controls
              </Link>
            </div>
          </div>
        )}
      </ConsentNudgePanel>
    );
  }

  return (
    <ConsentNudgePanel personalizationOn={false} onExitComplete={() => persistDismiss(false)}>
      {(requestClose) => (
        <div className={pop}>
          <DismissNoticeButton onDismiss={requestClose} />
          <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            <span className="text-pretty text-[0.8125rem] leading-relaxed tracking-body text-ink/88">
              Personalization is off—generic ranking and rails until you enable the demo scope.
            </span>
            <button
              type="button"
              className={`${tw.buttonEditorialBagSm} shrink-0 self-start sm:self-auto`}
              onClick={() => {
                updateConsent.mutate(["analytics", "personalization"]);
                track({
                  customer_id: "demo-customer-1",
                  event_type: "consent_updated",
                  payload: { scopes: ["analytics", "personalization"] },
                  consent_scope: ["analytics", "personalization"],
                });
              }}
            >
              Enable demo consent
            </button>
          </div>
        </div>
      )}
    </ConsentNudgePanel>
  );
}

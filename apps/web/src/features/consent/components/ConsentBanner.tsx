import { useEffect, useReducer, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Link } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";
import { useConsentMutation, useConsentQuery } from "@/features/consent/useConsent";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import { tw } from "@/shared/ui/tw";

const SESSION_DISMISS_PREFIX = "hyperpersona-consent-banner-dismissed";

/**
 * Three banner states:
 *   - "missing"   → no consent record yet (first-time user); offer setup CTA
 *   - "personal-on"  → personalization scope present; reassure + link to controls
 *   - "personal-off" → record exists but personalization off; offer one-click enable
 */
type BannerVariant = "missing" | "personal-on" | "personal-off";

function dismissStorageKey(variant: BannerVariant) {
  return `${SESSION_DISMISS_PREFIX}:${variant}`;
}

function readDismissed(variant: BannerVariant) {
  if (typeof window === "undefined") return false;
  try {
    return window.sessionStorage.getItem(dismissStorageKey(variant)) === "1";
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
  variant: BannerVariant;
  onExitComplete: () => void;
  children: (requestClose: () => void) => React.ReactNode;
};

function ConsentNudgePanel({ variant, onExitComplete, children }: NudgePanelProps) {
  const reduceMotion = useReducedMotion();
  const [open, setOpen] = useState(true);

  useEffect(() => {
    setOpen(true);
  }, [variant]);

  const handleDismiss = () => {
    setOpen(false);
  };

  return (
    <div className={toastAnchor}>
      <AnimatePresence onExitComplete={onExitComplete}>
        {open ? (
          <motion.div
            key={variant}
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
  const { isAuthenticated, customerId } = useAuth();
  const track = useTrackEvent();
  const [, forceRerender] = useReducer((c: number) => c + 1, 0);
  const consent = useConsentQuery();
  const updateConsent = useConsentMutation();

  // Unauthenticated visitors don't have a consent record at all — keep the
  // banner silent. The marketing/auth pages own their own messaging.
  if (!isAuthenticated) return null;

  // Either still loading, or a fatal error we don't want to surface as a
  // floating toast (the page-level surface owns that messaging).
  if (consent.isPending || consent.isFatalError) return null;

  const variant: BannerVariant = consent.isMissing
    ? "missing"
    : consent.record?.scopes.includes("personalization")
      ? "personal-on"
      : "personal-off";

  if (readDismissed(variant)) return null;

  const persistDismiss = () => {
    try {
      window.sessionStorage.setItem(dismissStorageKey(variant), "1");
    } catch {
      /* private mode / quota */
    }
    forceRerender();
  };

  if (variant === "missing") {
    return (
      <ConsentNudgePanel variant={variant} onExitComplete={persistDismiss}>
        {(requestClose) => (
          <div className={`${pop} ring-1 ring-info/12`}>
            <DismissNoticeButton onDismiss={requestClose} />
            <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
              <span className="text-pretty text-[0.8125rem] font-medium leading-relaxed tracking-body text-ink/88">
                You don&apos;t have a consent record yet. Set one up to control what the demo can use.
              </span>
              <Link
                to="/consent"
                className={`${tw.buttonEditorialBagSm} shrink-0 self-start sm:self-auto`}
              >
                Set up consent
              </Link>
            </div>
          </div>
        )}
      </ConsentNudgePanel>
    );
  }

  if (variant === "personal-on") {
    return (
      <ConsentNudgePanel variant={variant} onExitComplete={persistDismiss}>
        {(requestClose) => (
          <div className={`${pop} ring-1 ring-success/12`}>
            <DismissNoticeButton onDismiss={requestClose} />
            <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
              <span className="text-pretty text-[0.8125rem] font-medium leading-relaxed tracking-body text-ink/88">
                Personalization is on — ranking and search may use consented activity.
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

  // personal-off
  return (
    <ConsentNudgePanel variant={variant} onExitComplete={persistDismiss}>
      {(requestClose) => (
        <div className={pop}>
          <DismissNoticeButton onDismiss={requestClose} />
          <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            <span className="text-pretty text-[0.8125rem] leading-relaxed tracking-body text-ink/88">
              Personalization is off — generic ranking and rails until you enable the demo scope.
            </span>
            <button
              type="button"
              className={`${tw.buttonEditorialBagSm} shrink-0 self-start sm:self-auto`}
              disabled={updateConsent.isPending}
              onClick={() => {
                const nextScopes = ["analytics", "personalization"];
                const retention = consent.record?.data_retention_days ?? 90;
                updateConsent.mutate({ scopes: nextScopes, data_retention_days: retention });
                track({
                  customer_id: customerId ?? "demo-customer-1",
                  event_type: "consent_updated",
                  payload: { scopes: nextScopes, data_retention_days: retention, source: "banner" },
                  consent_scope: nextScopes,
                });
              }}
            >
              {updateConsent.isPending ? "Enabling…" : "Enable demo consent"}
            </button>
          </div>
        </div>
      )}
    </ConsentNudgePanel>
  );
}

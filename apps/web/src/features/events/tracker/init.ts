/**
 * One-shot boot for the event tracker. Wires:
 *   - Initial purge of stale/cross-identity rows + drain.
 *   - `visibilitychange` (tab hidden) + `pagehide` → keepalive flush so the
 *     last actions of the session don't get lost on close/reload.
 *   - `online` → resume draining once the network is back.
 *   - Auth lifecycle events (`auth:login`, `auth:logout`, `auth:expired`)
 *     so identity changes purge the queue and resume cleanly.
 *
 * This module must be imported exactly once during app boot. Calling
 * `initEventTracker()` twice is a no-op (idempotent).
 */

import {
  clearTrackerQueue,
  flushPending,
  trackerBootDrain,
} from "@/features/events/tracker/tracker";

let booted = false;

export function initEventTracker(): void {
  if (booted || typeof window === "undefined") return;
  booted = true;

  void trackerBootDrain();

  // Tab going to background → flush what we have. `visibilitychange` fires
  // before `pagehide` on most platforms; both are wired so we cover desktop
  // tab switches *and* mobile process kills.
  const onVisibilityChange = () => {
    if (document.visibilityState === "hidden") {
      void flushPending({ keepalive: true });
    }
  };
  document.addEventListener("visibilitychange", onVisibilityChange);

  const onPageHide = () => {
    // `keepalive: true` is the difference-maker here — without it, the
    // browser cancels in-flight fetches as the document unloads.
    void flushPending({ keepalive: true });
  };
  window.addEventListener("pagehide", onPageHide);

  const onOnline = () => {
    void flushPending();
  };
  window.addEventListener("online", onOnline);

  const onLogin = () => {
    // New session: requeue with the new identity in mind.
    void trackerBootDrain();
  };
  window.addEventListener("auth:login", onLogin);

  const onLogout = () => {
    // Stop pursuing flushes for the just-cleared session.
    void clearTrackerQueue();
  };
  window.addEventListener("auth:logout", onLogout);
  // Treat token expiry the same as a logout for the queue.
  window.addEventListener("auth:expired", onLogout);
}

import React from "react";
import ReactDOM from "react-dom/client";

import { AppProviders } from "@/app/providers";
import { router } from "@/app/router";
import { initEventTracker } from "@/features/events/tracker";
import "@/shared/styles/app.css";

async function bootstrap() {
  // Defensive cleanup: a previous MSW install may still be cached in the
  // browser from older builds. Unregister any service worker on boot so the
  // network panel never shows "(from service worker)" again.
  if (import.meta.env.DEV && "serviceWorker" in navigator) {
    try {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map((r) => r.unregister()));
    } catch {
      /* noop — old SW cleanup is best-effort. */
    }
  }

  // Wire DOM listeners (visibility/pagehide/online) and drain anything left
  // in IndexedDB from a previous session. Must run before the first event
  // fires so visibility-driven flushes see a populated queue.
  initEventTracker();

  const container = document.getElementById("root");
  if (!container) {
    throw new Error("Root container was not found");
  }

  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <AppProviders router={router} />
    </React.StrictMode>,
  );
}

void bootstrap();

import React from "react";
import ReactDOM from "react-dom/client";

import { AppProviders } from "@/app/providers";
import { router } from "@/app/router";
import { initEventTracker } from "@/features/events/tracker";
import "@/shared/styles/app.css";

async function bootstrap() {
  if (import.meta.env.DEV) {
    const { worker } = await import("@/mocks/browser");
    await worker.start({ onUnhandledRequest: "bypass" });
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

import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { useTrackEvent } from "@/features/events/useTrackEvent";

let lastTrackedPath = "";

export function PageViewTracker() {
  const location = useLocation();
  const track = useTrackEvent();

  useEffect(() => {
    const nextPath = `${location.pathname}${location.search}`;
    if (nextPath === lastTrackedPath) {
      return;
    }

    lastTrackedPath = nextPath;
    track({
      customer_id: "demo-customer-1",
      event_type: "page_view",
      payload: { path: nextPath },
      consent_scope: ["analytics", "personalization"],
    });
  }, [location.pathname, location.search, track]);

  return null;
}

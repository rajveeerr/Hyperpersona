import { useEffect } from "react";

import { useAuth } from "@/features/auth/useAuth";
import { useConsentQuery } from "@/features/consent/useConsent";
import { setConsentSnapshot } from "@/features/events/tracker";

/**
 * Bridges the consent React Query record into the imperative event tracker
 * so `trackEvent` calls can synchronously check whether personalization is
 * granted before persisting a row to IndexedDB.
 *
 * Mount once in the app shell. Renders nothing.
 */
export function TrackerConsentBridge() {
  const { isAuthenticated } = useAuth();
  const { record, isMissing } = useConsentQuery();

  useEffect(() => {
    // Unauthenticated or no record yet → no consent. The tracker drops events
    // until this snapshot grants `personalization`.
    if (!isAuthenticated) {
      setConsentSnapshot([]);
      return;
    }
    if (isMissing) {
      setConsentSnapshot([]);
      return;
    }
    if (record) {
      setConsentSnapshot(record.scopes);
    }
  }, [isAuthenticated, isMissing, record]);

  return null;
}

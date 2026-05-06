import { useSyncExternalStore } from "react";

import { getSession, isExpired, onSessionChange } from "@/features/auth/tokenStore";
import { apiClient } from "@/shared/api/client";
import type { AuthSession } from "@/shared/api/contracts";

/**
 * Single source of truth for the current session in React land.
 *
 * Backed by `tokenStore` via `useSyncExternalStore`, so:
 *  - cross-tab logout flips this immediately,
 *  - the snapshot is consistent with what `apiClient` will send on the wire,
 *  - components never read identity from URL/state directly.
 */
export function useAuth() {
  const session = useSyncExternalStore(onSessionChange, getSession, () => null);

  const expired = isExpired(session);
  const isAuthenticated = session !== null && !expired;

  return {
    session: isAuthenticated ? session : null,
    customerId: isAuthenticated ? session.customerId : null,
    email: isAuthenticated ? session.email : null,
    isAuthenticated,
    /** True when a session exists but has crossed its `expiresAtMs`. UI may prompt re-login. */
    isExpired: session !== null && expired,
    login: apiClient.login,
    register: apiClient.register,
    logout: apiClient.logout,
  };
}

/**
 * Imperative read for non-component code (event tracker, query factories).
 * Always returns the live session — never a stale React snapshot.
 */
export function readAuthSession(): AuthSession | null {
  const session = getSession();
  return session && !isExpired(session) ? session : null;
}

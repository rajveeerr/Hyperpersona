/**
 * Bearer-token session storage.
 *
 * Persists the JWT issued by `POST /login` / `POST /register` so the session
 * survives reloads, with cross-tab sync via the `storage` event. The shape and
 * rationale are documented in `apps/web/PHASE5_BACKEND_INTEGRATION_DISCOVERY.md`
 * under *Token storage strategy*.
 *
 * Threat model note: localStorage is reachable from any script on the origin.
 * Mitigations live at the app layer (CSP, no `dangerouslySetInnerHTML` on
 * user content, short JWT TTL). This module is the only place that touches
 * the storage key, so a future move to refresh tokens / HttpOnly cookies is
 * a one-file change.
 */

import type { AuthResponse, AuthSession } from "@/shared/api/contracts";

const STORAGE_KEY = "hyperpersona.auth.v1";

type Listener = (session: AuthSession | null) => void;

const listeners = new Set<Listener>();

function safeRead(): AuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AuthSession>;
    if (
      typeof parsed.token !== "string" ||
      typeof parsed.customerId !== "string" ||
      typeof parsed.email !== "string" ||
      typeof parsed.expiresAtMs !== "number"
    ) {
      return null;
    }
    return parsed as AuthSession;
  } catch {
    return null;
  }
}

let cached: AuthSession | null = safeRead();

function emit(next: AuthSession | null) {
  cached = next;
  for (const listener of listeners) listener(next);
}

if (typeof window !== "undefined") {
  // Cross-tab sync: another tab logged in/out → mirror that here.
  window.addEventListener("storage", (event) => {
    if (event.key && event.key !== STORAGE_KEY) return;
    emit(safeRead());
  });
}

export function getSession(): AuthSession | null {
  return cached;
}

export function setSession(session: AuthSession): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  }
  emit(session);
}

export function clearSession(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(STORAGE_KEY);
  }
  emit(null);
}

/**
 * Treat a session as expired `skewMs` before its real expiry so we proactively
 * re-auth instead of letting protected requests fail at the boundary.
 */
export function isExpired(session: AuthSession | null, skewMs = 30_000): boolean {
  if (!session) return true;
  return Date.now() + skewMs >= session.expiresAtMs;
}

export function onSessionChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Convert the server's `AuthResponse` into the FE `AuthSession` (computes `expiresAtMs`). */
export function sessionFromAuthResponse(res: AuthResponse): AuthSession {
  return {
    token: res.token,
    customerId: res.customer_id,
    email: res.email,
    expiresAtMs: Date.now() + res.expires_in * 1000,
  };
}

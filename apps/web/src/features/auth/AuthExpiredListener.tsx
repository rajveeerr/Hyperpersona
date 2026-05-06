import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { pushToast } from "@/features/toast/store";

const PUBLIC_ROUTES = new Set(["/login", "/register"]);

/**
 * Mounted once at the app shell. Listens for `auth:expired` (dispatched by the
 * API client when the JWT is rejected) and:
 *   - clears React Query caches scoped to the previous identity,
 *   - shows a toast,
 *   - routes the user to /login while preserving where they were.
 *
 * Mounted as a sibling to the route outlet so it can react regardless of the
 * route the 401 came from.
 */
export function AuthExpiredListener() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    function handleExpired() {
      queryClient.clear();
      if (PUBLIC_ROUTES.has(location.pathname)) return;
      pushToast("Your session expired. Sign in again to continue.");
      const from = `${location.pathname}${location.search}${location.hash}`;
      navigate("/login", { replace: true, state: { from } });
    }

    window.addEventListener("auth:expired", handleExpired);
    return () => {
      window.removeEventListener("auth:expired", handleExpired);
    };
  }, [navigate, queryClient, location.pathname, location.search, location.hash]);

  return null;
}

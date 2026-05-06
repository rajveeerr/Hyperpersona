import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";

type ProtectedRouteProps = {
  children: ReactNode;
};

/**
 * Gate a route on a valid session. Unauthenticated visitors are redirected to
 * `/login` with the original location stashed in route state so the login
 * mutation's success handler can return the user to where they were going.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    const from = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to="/login" replace state={{ from }} />;
  }

  return <>{children}</>;
}

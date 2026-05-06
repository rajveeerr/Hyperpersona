import { Suspense } from "react";
import { Outlet, useLocation, useNavigation } from "react-router-dom";

import { RouteFallback } from "@/app/RouteFallback";

/**
 * Wraps route output with (1) a light opacity dip while lazy chunks load and
 * (2) a short opacity snap on route changes. Respects `prefers-reduced-motion`
 * via CSS (see `app.css` `.outlet-route-snap`).
 */
export function OutletShell() {
  const location = useLocation();
  const navigation = useNavigation();
  const loadingRoute = navigation.state === "loading";

  return (
    <div
      className={[
        "transition-opacity duration-150 ease-out motion-reduce:transition-none",
        loadingRoute ? "opacity-[0.9] motion-reduce:opacity-100" : "opacity-100",
      ].join(" ")}
    >
      <div key={location.key} className="outlet-route-snap">
        <Suspense fallback={<RouteFallback />}>
          <Outlet />
        </Suspense>
      </div>
    </div>
  );
}

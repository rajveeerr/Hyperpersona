import { useLayoutEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

/**
 * Scroll window to top when the **route path** changes (real navigation).
 * Query-string-only updates (filters, sort, pagination on the same page) intentionally do **not** scroll —
 * those are in-place listing updates.
 */
export function ScrollToTop() {
  const { pathname } = useLocation();
  const prevPathnameRef = useRef<string | null>(null);

  useLayoutEffect(() => {
    const prev = prevPathnameRef.current;
    if (prev !== null && prev !== pathname) {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
    prevPathnameRef.current = pathname;
  }, [pathname]);

  return null;
}

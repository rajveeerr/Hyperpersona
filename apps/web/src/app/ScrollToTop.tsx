import { useLayoutEffect } from "react";
import { useLocation } from "react-router-dom";

/** Scroll window to top on route or query-string change — `useLayoutEffect` runs before paint to reduce scroll flash. */
export function ScrollToTop() {
  const { pathname, search } = useLocation();

  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [pathname, search]);

  return null;
}

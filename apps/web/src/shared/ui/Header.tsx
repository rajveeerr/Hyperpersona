import { FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";
import { useCartCount } from "@/features/cart/useCart";
import { useWishlistCount } from "@/features/wishlist/useWishlist";
import { tw } from "@/shared/ui/tw";

function BagIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M6 7h12l-1 12H7L6 7Z" />
      <path d="M9 7V5a3 3 0 0 1 6 0v2" />
    </svg>
  );
}

export function Header() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAuthenticated, email, logout } = useAuth();
  const cartCount = useCartCount();
  const wishlistCount = useWishlistCount();

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const query = String(data.get("q") ?? "").trim();
    if (!query) return;
    // Spec `search` event is emitted from `SearchPageListing` once results
    // land (so `results_count` is accurate). This handler just navigates.
    navigate(`/search?q=${encodeURIComponent(query)}`);
  }

  function handleSignOut() {
    logout();
    queryClient.clear();
    navigate("/", { replace: true });
  }

  return (
    <header
      className={`${tw.heroCanvas} fixed inset-x-0 top-0 z-50 w-full`}
    >
      <div
        className={`${tw.layoutFrame} grid grid-cols-1 items-center gap-y-4 py-4 md:grid-cols-[minmax(0,auto)_1fr_minmax(0,auto)] md:gap-x-10 md:gap-y-0 md:py-4`}
      >
        <Link
          to="/"
          prefetch="intent"
          className={`${tw.displayWordmarkNav} text-[1.35rem] sm:text-[1.5rem] md:justify-self-start`}
        >
          hyperpersona
        </Link>

        <nav
          className="flex flex-wrap justify-center gap-x-6 gap-y-2 md:justify-center"
          aria-label="Primary"
        >
          <NavLink to="/catalog" prefetch="intent" className="nav-link-quiet">
            Catalog
          </NavLink>
          <NavLink to="/profile" prefetch="intent" className="nav-link-quiet">
            Profile
          </NavLink>
          <NavLink to="/consent" prefetch="intent" className="nav-link-quiet">
            Consent
          </NavLink>
          <NavLink to="/demo" prefetch="intent" className="nav-link-quiet">
            Demo
          </NavLink>
          <NavLink to="/wishlist" prefetch="intent" className="nav-link-quiet">
            Wishlist ({wishlistCount})
          </NavLink>
        </nav>

        <div className="flex flex-wrap items-center justify-center gap-6 md:justify-end">
          <form
            onSubmit={onSubmit}
            className="flex min-w-0 max-w-[min(100%,280px)] items-center gap-2 rounded-pill border border-outline/60 bg-surface-strong/60 px-3 py-1.5 transition-[box-shadow,border-color] focus-within:border-ink/30 focus-within:ring-2 focus-within:ring-accent/35"
          >
            <label className="sr-only" htmlFor="global-search">
              Search demo products
            </label>
            <input
              id="global-search"
              name="q"
              type="search"
              autoComplete="off"
              placeholder="Search…"
              className="min-w-0 flex-1 border-0 bg-transparent py-0.5 text-[0.8125rem] text-ink outline-none placeholder:text-muted/60"
            />
            <button type="submit" className={tw.navSearchSubmit}>
              Go
            </button>
          </form>

          {isAuthenticated ? (
            <div className="flex items-center gap-2.5" aria-label="Account">
              <span
                className="hidden max-w-[16ch] truncate text-[0.75rem] font-medium tracking-[0.02em] text-muted sm:inline"
                title={email ?? undefined}
              >
                {email}
              </span>
              <span aria-hidden className="hidden h-3 w-px bg-outline/60 sm:inline-block" />
              <button
                type="button"
                onClick={handleSignOut}
                className="nav-link-quiet inline-flex cursor-pointer items-center border-0 bg-transparent no-underline"
              >
                Sign out
              </button>
            </div>
          ) : (
            <NavLink
              to="/login"
              prefetch="intent"
              className="nav-link-quiet inline-flex items-center gap-1.5 border-0 bg-transparent no-underline"
            >
              Sign in
            </NavLink>
          )}

          <Link
            to="/cart"
            prefetch="intent"
            className="nav-link-quiet inline-flex items-center gap-1.5 border-0 bg-transparent no-underline"
          >
            <BagIcon />
            <span>Bag{cartCount > 0 ? ` (${cartCount})` : ""}</span>
          </Link>
        </div>
      </div>
    </header>
  );
}

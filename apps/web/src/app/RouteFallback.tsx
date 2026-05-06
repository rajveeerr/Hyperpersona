import { tw } from "@/shared/ui/tw";

/**
 * Suspense fallback for lazy route segments — **fixed min-height** to limit main-column layout shift
 * (Vercel: avoid jarring height collapse while chunks load).
 */
export function RouteFallback() {
  return (
    <div
      className={`${tw.stackLg} min-h-[min(72vh,860px)] w-full max-w-3xl pt-6 sm:pt-8`}
      aria-busy
      aria-label="Loading page"
    >
      <div className="h-9 w-40 max-w-[min(100%,14rem)] animate-pulse rounded-md bg-ink/7" />
      <div className="h-[min(42vh,420px)] w-full max-w-xl animate-pulse rounded-[max(var(--radius-inner),1rem)] bg-ink/6" />
      <div className="grid max-w-xl gap-3">
        <div className="h-4 w-full animate-pulse rounded bg-ink/6" />
        <div className="h-4 w-[85%] animate-pulse rounded bg-ink/6" />
        <div className="h-4 w-[70%] animate-pulse rounded bg-ink/6" />
      </div>
    </div>
  );
}

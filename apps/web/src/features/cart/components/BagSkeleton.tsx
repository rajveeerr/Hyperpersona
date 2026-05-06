const pulse = "animate-pulse rounded-md bg-ink/6";

export function BagSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="grid gap-0 border-l border-t border-[#e5e5e5]" aria-busy aria-label="Loading bag">
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="flex flex-wrap items-center justify-between gap-6 border-r border-b border-[#e5e5e5] px-5 py-8 sm:px-7 sm:py-10"
        >
          <div className="flex min-w-0 flex-1 items-center gap-5">
            <div className={`size-20 shrink-0 rounded-lg ${pulse} sm:size-24`} />
            <div className="grid min-w-0 flex-1 gap-2">
              <div className={`h-4 w-48 max-w-full ${pulse}`} />
              <div className={`h-3 w-24 ${pulse}`} />
            </div>
          </div>
          <div className={`h-10 w-32 rounded-pill ${pulse}`} />
        </div>
      ))}
    </div>
  );
}

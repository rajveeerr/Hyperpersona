import { tw } from "@/shared/ui/tw";

const pulse = "animate-pulse rounded-md bg-ink/6";

export function ProfileLabSkeleton() {
  return (
    <div className={`${tw.stackLg}`} aria-busy aria-label="Loading profile lab">
      <div className="max-w-3xl space-y-3">
        <div className={`h-3 w-28 ${pulse}`} />
        <div className={`h-10 w-full max-w-xl ${pulse}`} />
        <div className={`h-4 w-full max-w-2xl ${pulse}`} />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={`${tw.labPanel} ${tw.labPanelPad} space-y-4`}>
            <div className={`h-3 w-36 ${pulse}`} />
            <div className={`h-8 w-56 max-w-full ${pulse}`} />
            <div className={`h-3 w-full max-w-md ${pulse}`} />
            <div className={`h-3 w-[88%] max-w-md ${pulse}`} />
          </div>
        ))}
      </div>
    </div>
  );
}

import { formatConfidence } from "@/shared/lib/format";
import type { RecommendationRail } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

type RecommendationAuditDrawerProps = {
  rail: RecommendationRail;
  open: boolean;
  onClose: () => void;
};

export function RecommendationAuditDrawer({ rail, open, onClose }: RecommendationAuditDrawerProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-70 flex" role="dialog" aria-modal="true" aria-label="Recommendation audit">
      <button
        type="button"
        className="h-full flex-1 bg-black/25 backdrop-blur-[1px]"
        aria-label="Close recommendation audit"
        onClick={onClose}
      />
      <aside className="h-full w-[min(28rem,94vw)] overflow-auto border-l border-outline/20 bg-canvas px-5 py-6 shadow-[0_28px_72px_rgba(34,28,23,0.18)] sm:px-6 sm:py-7">
        <div className="flex items-start justify-between gap-3 border-b border-outline/20 pb-4">
          <div>
            <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>Recommendation audit</p>
            <h3 className={`${tw.displayH2} mt-1 text-xl`}>{rail.title}</h3>
          </div>
          <button type="button" onClick={onClose} className={tw.buttonGhost}>
            Close
          </button>
        </div>

        <div className="mt-5 grid gap-5">
          <section className="rounded-card border border-outline/20 bg-white/65 p-4">
            <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>Mode</p>
            <p className="mt-2 text-sm text-ink/90">{rail.fallback ? "Generic fallback" : "Personalized"}</p>
            <p className={`mt-1 text-sm ${tw.muted}`}>
              {rail.fallback ? "Consent/signals are insufficient, so generic merchandising is used." : formatConfidence(rail.confidence)}
            </p>
          </section>

          <section className="rounded-card border border-outline/20 bg-white/65 p-4">
            <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>Reason string</p>
            <p className="mt-2 text-sm leading-relaxed text-ink/88">{rail.reason}</p>
          </section>

          <section className="rounded-card border border-outline/20 bg-white/65 p-4">
            <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>Products considered</p>
            <ul className="m-0 mt-2 list-none space-y-2 p-0">
              {rail.products.slice(0, 5).map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 border-b border-outline/10 pb-2 last:border-b-0 last:pb-0">
                  <span className="min-w-0 truncate text-sm text-ink/90">{p.name}</span>
                  <span className={`shrink-0 text-xs ${tw.muted}`}>{p.brand}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </aside>
    </div>
  );
}


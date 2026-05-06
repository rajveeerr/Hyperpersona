import { useTrackEvent } from "@/features/events/useTrackEvent";
import { demoPersonas } from "@/features/personas/data";
import { useCurrentPersona, usePersonaStore } from "@/features/personas/store";
import { tw } from "@/shared/ui/tw";

function CheckMark({ className }: { className?: string }) {
  return (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M20 6L9 17l-5-5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

type PersonaSwitcherProps = {
  /** Nested in profile lab—outer chrome is provided by the parent shell. */
  embedded?: boolean;
};

export const PersonaSwitcher = ({ embedded = false }: PersonaSwitcherProps) => {
  const persona = useCurrentPersona();
  const setPersona = usePersonaStore((state) => state.setPersona);
  const track = useTrackEvent();

  const shell = embedded
    ? "overflow-hidden bg-transparent shadow-none ring-0"
    : "overflow-hidden rounded-[0.65rem] ring-1 ring-outline/18 shadow-[0_14px_42px_rgba(34,28,23,0.06)]";

  return (
    <div className={shell}>
      <nav aria-label="Sample shopper profiles" className="flex flex-col bg-white/40">
        {demoPersonas.map((item) => {
          const selected = item.id === persona.id;
          return (
            <button
              key={item.id}
              type="button"
              className={`group flex w-full items-start gap-3 border-b border-outline/10 px-3 py-3.5 text-left transition-[background-color,box-shadow,transform,border-color] duration-200 ease-out last:border-b-0 motion-safe:active:scale-[0.992] sm:gap-3.5 sm:px-3.5 sm:py-4 ${
                selected
                  ? "border-l-4 border-l-accent bg-linear-to-r from-[color-mix(in_srgb,var(--color-accent)_11%,transparent)] via-[color-mix(in_srgb,var(--color-accent)_4%,transparent)] to-transparent shadow-[inset_0_1px_0_rgba(255,252,247,0.65)]"
                  : "border-l-4 border-l-transparent hover:bg-ink/[0.035]"
              }`}
              onClick={() => {
                setPersona(item.id);
                track({
                  customer_id: "demo-customer-1",
                  event_type: "persona_switched",
                  payload: { personaId: item.id, label: item.label },
                  consent_scope: ["analytics", "personalization"],
                });
              }}
              aria-pressed={selected}
            >
              <span className="min-w-0 flex-1">
                <span
                  className={`block text-[0.8125rem] tracking-[0.02em] ${selected ? "font-semibold text-ink" : "font-medium text-ink/88"}`}
                >
                  {item.label}
                </span>
                <span className={`mt-1 block text-pretty text-[0.78rem] leading-snug sm:text-[0.8125rem] ${tw.muted}`}>
                  {item.summary}
                </span>
              </span>
              <span
                className={`flex shrink-0 self-center transition-[opacity,transform] duration-200 ${
                  selected ? "text-accent-strong opacity-100" : "text-ink/0 opacity-0 group-hover:text-ink/25 group-hover:opacity-100"
                }`}
                aria-hidden
              >
                <CheckMark className="size-4.5 sm:size-5" />
              </span>
            </button>
          );
        })}
      </nav>
      <div className="border-t border-outline/12 bg-ink/2.5 px-3 py-2.5 sm:px-3.5">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-accent-strong">
          Active profile · {persona.label}
        </p>
        <p key={persona.id} className="sr-only" aria-live="polite" aria-atomic="true">
          Profile switched to {persona.label}. Memory and rails now follow this shopper.
        </p>
      </div>
    </div>
  );
};

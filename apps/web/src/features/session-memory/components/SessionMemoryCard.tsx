import { useCurrentPersona } from "@/features/personas/store";
import { tw } from "@/shared/ui/tw";

type SessionMemoryCardProps = {
  /** Sits flush under persona list—no top rule so it reads as one control block. */
  embedded?: boolean;
};

export const SessionMemoryCard = ({ embedded = false }: SessionMemoryCardProps) => {
  const persona = useCurrentPersona();

  return (
    <div
      className={
        embedded
          ? "bg-ink/2.5 px-3 pt-4 pb-2 sm:px-3.5 sm:pt-5 sm:pb-3"
          : "border-t border-outline/12 pt-5 sm:pt-6"
      }
    >
      <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>What we infer now</p>
      <div key={persona.id} className="persona-memory-snap">
        <p className={`text-pretty text-sm leading-relaxed sm:text-[0.9375rem] sm:leading-relaxed ${tw.muted}`}>
          {persona.currentIntent}
        </p>
        <ul className="m-0 mt-3 flex list-none flex-col gap-2 border-t border-outline/10 pt-3 p-0 sm:mt-4 sm:gap-2.5 sm:pt-4">
          {persona.recentSignals.map((signal) => (
            <li key={`${persona.id}-${signal}`} className="flex gap-2.5 text-[0.8125rem] leading-relaxed text-ink/88">
              <span className={`shrink-0 select-none ${tw.muted}`} aria-hidden>
                —
              </span>
              <span className="min-w-0">{signal}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};


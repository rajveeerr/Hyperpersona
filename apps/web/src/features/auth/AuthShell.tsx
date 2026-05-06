import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { tw } from "@/shared/ui/tw";

const panelShell =
  "rounded-[max(var(--radius-inner),1rem)] border border-outline/35 bg-surface-strong/75 px-6 py-7 shadow-[0_1px_0_rgba(34,28,23,0.06)] ring-1 ring-inset ring-white/55 backdrop-blur-[10px] sm:px-8 sm:py-8";

type AuthShellProps = {
  eyebrow: string;
  title: string;
  intro: string;
  altPrompt: { text: string; linkLabel: string; to: string };
  formError?: string | null;
  busy?: boolean;
  submitLabel: string;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
};

/**
 * Shared layout chrome for `/login` and `/register`. Page components own the
 * form fields + validation; this shell only contributes the editorial header,
 * panel surface, error/help slots, and the submit row so visual choices stay
 * in one place.
 */
export function AuthShell({
  eyebrow,
  title,
  intro,
  altPrompt,
  formError,
  busy,
  submitLabel,
  onSubmit,
  children,
}: AuthShellProps) {
  return (
    <div className={`${tw.stackLg} mx-auto w-full max-w-xl pt-8 pb-12 sm:pt-10 lg:pt-12 sm:pb-14 lg:pb-16`}>
      <header>
        <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>{eyebrow}</p>
        <h1 className={`${tw.storyTitle} max-w-[22ch]`}>{title}</h1>
        <p className={`mt-4 max-w-md text-pretty text-sm leading-relaxed ${tw.muted}`}>{intro}</p>
      </header>

      <form className={`${panelShell} ${tw.stackMd}`} onSubmit={onSubmit} noValidate>
        {children}

        {formError ? (
          <p className="text-sm text-red-800/90" role="alert">
            {formError}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-4 border-t border-outline/15 pt-6">
          <button type="submit" className={tw.buttonEditorialBag} disabled={busy}>
            {busy ? "Working…" : submitLabel}
          </button>
          <p className={`text-sm ${tw.muted}`}>
            {altPrompt.text}{" "}
            <Link to={altPrompt.to} className="font-medium text-ink underline decoration-ink/30 underline-offset-[0.32rem]">
              {altPrompt.linkLabel}
            </Link>
          </p>
        </div>
      </form>
    </div>
  );
}

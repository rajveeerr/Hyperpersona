import type { ReactNode } from "react";

type PageShellProps = {
  children: ReactNode;
};

/** Viewport-wide max rail — gutters live on `main` (`layoutGutterX`) so breakouts are not double-padded. */
export function PageShell({ children }: PageShellProps) {
  return (
    <div className="mx-auto flex w-full max-w-[min(90rem,calc(100vw-2rem))] flex-1 flex-col pb-0 pt-0">
      {children}
    </div>
  );
}

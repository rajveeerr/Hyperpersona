import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import { useToastStore } from "@/features/toast/store";

/**
 * Short-lived commerce toasts (bag / wishlist). Bottom-centered, above debug FAB (`z-60`).
 */
export function ToastViewport() {
  const items = useToastStore((s) => s.items);
  const dismiss = useToastStore((s) => s.dismiss);
  const reduce = useReducedMotion();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return null;
  }

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-24 z-[55] flex flex-col items-center gap-2 px-4 sm:bottom-10"
      aria-live="polite"
      aria-relevant="additions text"
    >
      <AnimatePresence mode="popLayout">
        {items.map((t) => (
          <motion.div
            key={t.id}
            layout
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: 10 }}
            animate={reduce ? { opacity: 1 } : { opacity: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: 6 }}
            transition={
              reduce
                ? { duration: 0.18, ease: [0.22, 1, 0.36, 1] }
                : { type: "spring", stiffness: 420, damping: 28, mass: 0.72 }
            }
            className="pointer-events-auto w-full max-w-md cursor-default rounded-pill border border-outline/45 bg-surface-strong/95 px-5 py-3 text-center text-sm font-medium tracking-body text-ink shadow-[0_16px_48px_rgba(34,28,23,0.08)] backdrop-blur-sm"
            onClick={() => dismiss(t.id)}
          >
            {t.message}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

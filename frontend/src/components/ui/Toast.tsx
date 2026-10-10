import { AnimatePresence, motion } from "framer-motion";
import { cx } from "@/lib/cx";
import { useToasts } from "./toastStore";

const toneClass = {
  info: "border-line bg-ink text-paper",
  success: "border-pine bg-ink text-paper",
  error: "border-berry bg-berry text-white",
};

export function ToastRegion() {
  const { toasts, dismiss } = useToasts();
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4 md:bottom-6 md:items-end"
    >
      <AnimatePresence initial={false}>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            role={t.tone === "error" ? "alert" : "status"}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={cx(
              "pointer-events-auto flex w-full max-w-sm items-center gap-3 rounded-md border-l-4 px-4 py-3 text-sm shadow-lg",
              toneClass[t.tone],
            )}
          >
            <span className="flex-1">{t.message}</span>
            {t.action && (
              <button
                type="button"
                className="min-h-11 rounded-sm px-2 font-bold underline underline-offset-2"
                onClick={() => {
                  t.action?.run();
                  dismiss(t.id);
                }}
              >
                {t.action.label}
              </button>
            )}
            <button
              type="button"
              aria-label="Dismiss"
              className="min-h-11 min-w-11 rounded-sm opacity-80 hover:opacity-100"
              onClick={() => dismiss(t.id)}
            >
              ×
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

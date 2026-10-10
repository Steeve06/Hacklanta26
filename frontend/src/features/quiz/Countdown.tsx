import { useEffect } from "react";
import { cx } from "@/lib/cx";
import { useNow } from "@/lib/useNow";

/** Time left in a try, by the server's clock. Calls `onExpire` once when it reaches zero so the
 * page can fetch the settled result. */
export function Countdown({ expiresAt, onExpire }: { expiresAt: string; onExpire: () => void }) {
  const now = useNow(1000);
  const left = Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 1000));
  useEffect(() => {
    if (left > 0) return;
    const timer = window.setTimeout(onExpire, 11_000);
    return () => window.clearTimeout(timer);
  }, [left, onExpire]);
  const minutes = Math.floor(left / 60);
  const seconds = String(left % 60).padStart(2, "0");
  return (
    <span
      role="timer"
      aria-label={left > 0 ? `${minutes} minutes ${seconds} seconds left` : "Time's up"}
      className={cx(
        "font-display font-extrabold tabular-nums",
        left <= 30 ? "text-berry" : "text-ink",
      )}
    >
      {left > 0 ? `${minutes}:${seconds}` : "Time's up"}
    </span>
  );
}

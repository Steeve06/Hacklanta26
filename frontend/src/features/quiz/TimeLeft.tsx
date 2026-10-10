import { cx } from "@/lib/cx";
import { formatClock, useCountdown } from "@/lib/useCountdown";

export function TimeLeft({ closesAt }: { closesAt: string }) {
  const remaining = useCountdown(closesAt) ?? 0;
  const hours = Math.floor(remaining / 3_600_000);
  const text =
    hours >= 1
      ? `${hours} h ${Math.floor((remaining % 3_600_000) / 60_000)} min left`
      : `${formatClock(remaining)} left`;
  return (
    <span className={cx("font-bold tabular-nums", hours < 4 ? "text-berry" : "text-ink-soft")}>
      {text}
    </span>
  );
}

import { Icon } from "@/components/Icon";
import { cx } from "@/lib/cx";
import type { Streak, StreakDay } from "./api";
import { formatDeckDay } from "./topics";

export function StreakBadge({ streak, compact = false }: { streak: Streak; compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span
        className={cx(
          "flex items-center justify-center rounded-full",
          streak.done_today ? "bg-mustard-soft text-mustard-ink" : "bg-sunken text-ink-faint",
          compact ? "h-11 w-11" : "h-14 w-14",
        )}
      >
        <Icon name="flame" className={compact ? "h-6 w-6" : "h-8 w-8"} />
      </span>
      <div>
        <p
          className={cx(
            "font-display font-extrabold leading-none",
            compact ? "text-xl" : "text-3xl",
          )}
        >
          {streak.current}
          <span className="ml-1 text-base font-bold text-ink-soft">
            {streak.current === 1 ? "day" : "days"} in a row
          </span>
        </p>
        {!compact && (
          <p className="text-sm text-ink-soft">
            Best {streak.longest} · {streak.freezes} {streak.freezes === 1 ? "freeze" : "freezes"}{" "}
            saved
          </p>
        )}
      </div>
    </div>
  );
}

const DAY_STYLES: Record<StreakDay["result"], string> = {
  done: "bg-mustard text-ink",
  frozen: "bg-pine-soft text-pine-strong",
  missed: "bg-berry-soft text-berry",
  open: "border-2 border-dashed border-ink-faint text-ink-soft",
  none: "bg-sunken text-ink-faint",
};

const DAY_LABELS: Record<StreakDay["result"], string> = {
  done: "done",
  frozen: "freeze used",
  missed: "missed",
  open: "today, not done yet",
  none: "no deck",
};

export function WeekStrip({ week }: { week: StreakDay[] }) {
  return (
    <ol className="flex gap-2" aria-label="The last seven days">
      {week.map((d) => (
        <li key={d.day} className="flex flex-col items-center gap-1">
          <span
            className={cx(
              "flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold",
              DAY_STYLES[d.result],
            )}
            title={DAY_LABELS[d.result]}
          >
            {d.result === "done" ? (
              <Icon name="flame" className="h-4 w-4" />
            ) : d.result === "frozen" ? (
              "❄"
            ) : (
              formatDeckDay(d.day, { day: "numeric" })
            )}
            <span className="sr-only">
              {formatDeckDay(d.day, { weekday: "long" })}: {DAY_LABELS[d.result]}
            </span>
          </span>
          <span aria-hidden="true" className="text-xs text-ink-soft">
            {formatDeckDay(d.day, { weekday: "narrow" })}
          </span>
        </li>
      ))}
    </ol>
  );
}

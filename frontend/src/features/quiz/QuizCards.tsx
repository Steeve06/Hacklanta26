import { Link } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { formatExact, useTimezone } from "@/lib/time";
import { formatClock, useCountdown } from "@/lib/useCountdown";
import { cx } from "@/lib/cx";
import type { Quiz, Streak } from "./api";
import { quizName } from "./quizName";

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

export function OpenQuizRow({ quiz }: { quiz: Quiz }) {
  return (
    <Link
      to={`/pulse/quiz/${quiz.id}`}
      className="flex min-h-11 items-center justify-between gap-3 rounded-md border border-line bg-surface px-3 py-2 hover:border-ink-faint"
    >
      <span className="flex flex-col">
        <span className="font-bold">{quizName(quiz)}</span>
        <span className="text-sm">
          {quiz.question_count} questions · <TimeLeft closesAt={quiz.closes_at} />
        </span>
      </span>
      <Icon name="chevron" className="h-5 w-5 text-ink-faint" />
    </Link>
  );
}

export function UpcomingQuizRow({ quiz }: { quiz: Quiz }) {
  const tz = useTimezone();
  return (
    <li className="flex flex-wrap justify-between gap-2 py-2 text-sm">
      <span className="font-bold">{quizName(quiz)}</span>
      <span className="text-ink-soft">Opens {formatExact(quiz.opens_at, tz)}</span>
    </li>
  );
}

export function StreakBadge({ streak, compact = false }: { streak: Streak; compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span
        className={cx(
          "flex items-center justify-center rounded-full bg-mustard-soft text-mustard-ink",
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
            {streak.current === 1 ? "quiz" : "quizzes"} in a row
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

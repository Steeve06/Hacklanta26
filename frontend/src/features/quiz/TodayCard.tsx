import { Link } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { cx } from "@/lib/cx";
import { useTimezone } from "@/lib/time";
import type { DeckDetail } from "./api";
import { focusLine, sessionLine } from "./topics";

export function TodayCard({ deck }: { deck: DeckDetail }) {
  const tz = useTimezone();
  const done = Boolean(deck.completed_at);
  const answered = deck.items.filter((i) => i.answered).length;
  const left = deck.question_count - answered;
  return (
    <Link
      to="/pulse/quiz/today"
      className={cx(
        "flex min-h-11 items-center justify-between gap-3 rounded-md border px-3 py-2 hover:border-ink-faint",
        done ? "border-line bg-surface" : "border-mustard bg-mustard-soft",
      )}
    >
      <span className="flex flex-col">
        <span className="font-bold">
          {done
            ? "Today's quiz is done"
            : deck.started_at
              ? "Finish today's quiz"
              : "Start today's quiz"}
        </span>
        <span className="text-sm font-bold text-pine">{focusLine(deck.focus, tz)}</span>
        <span className="text-sm text-ink-soft">
          {done
            ? `${deck.knew} of ${deck.question_count} correct, +${deck.xp} XP. See you tomorrow.`
            : deck.started_at
              ? `${left} ${left === 1 ? "question" : "questions"} to go, the clock is running`
              : sessionLine(deck)}
        </span>
      </span>
      <Icon name={done ? "check" : "chevron"} className="h-5 w-5 shrink-0 text-ink-faint" />
    </Link>
  );
}

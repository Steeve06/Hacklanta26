import { Link } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { cx } from "@/lib/cx";
import { useTimezone } from "@/lib/time";
import type { DeckDetail } from "./api";
import { focusLine } from "./topics";

export function TodayCard({ deck }: { deck: DeckDetail }) {
  const tz = useTimezone();
  const done = Boolean(deck.completed_at);
  const reviewed = deck.cards.filter((c) => c.knew !== null).length;
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
            ? "Today's deck is done"
            : reviewed
              ? "Finish today's flashcards"
              : "Start today's flashcards"}
        </span>
        <span className="text-sm font-bold text-pine">{focusLine(deck.focus, tz)}</span>
        <span className="text-sm text-ink-soft">
          {done
            ? `${deck.knew} of ${deck.card_count} known. See you tomorrow.`
            : `${deck.card_count - reviewed} ${deck.card_count - reviewed === 1 ? "card" : "cards"} to go, about 3 minutes`}
        </span>
      </span>
      <Icon name={done ? "check" : "chevron"} className="h-5 w-5 text-ink-faint" />
    </Link>
  );
}

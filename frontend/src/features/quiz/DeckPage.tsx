import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { Confetti } from "@/components/Confetti";
import { Icon } from "@/components/Icon";
import { Mascot } from "@/components/mascot/Mascot";
import { Button, ProgressBar, QueryView, Skeleton, toast } from "@/components/ui";
import { useNumericParam } from "@/features/lms/useIds";
import { cx } from "@/lib/cx";
import { useTimezone } from "@/lib/time";
import {
  useAnswer,
  useDeck,
  useRefreshDeck,
  useStartDeck,
  useTodayDeck,
  type DeckDetail,
  type DeckItem,
  type ItemResponse,
  type Solution,
} from "./api";
import { Feedback, ItemView } from "./Items";
import { focusLine, formatDeckDay, sessionLine, TYPE_LABELS, XP_PER_CORRECT } from "./topics";

export function TodayDeckPage() {
  return <DeckView query={useTodayDeck()} />;
}

export function DeckPage() {
  return <DeckView query={useDeck(useNumericParam("deckId"))} />;
}

function DeckView({ query }: { query: ReturnType<typeof useTodayDeck> }) {
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <Breadcrumbs
        items={[
          { label: "Quiz", to: "/pulse/quiz" },
          { label: query.data ? deckTitle(query.data) : "Quiz session" },
        ]}
      />
      <QueryView
        query={query}
        skeleton={
          <div className="flex flex-col gap-3">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-64 w-full" />
          </div>
        }
      >
        {(deck) => <Session key={deck.id} deck={deck} />}
      </QueryView>
    </div>
  );
}

function deckTitle(deck: DeckDetail): string {
  return `Quiz for ${formatDeckDay(deck.day, { weekday: "long", month: "short", day: "numeric" })}`;
}

/** Intro, then one question at a time against the clock, then the results. After a graded
 * question, its feedback stays up until the student moves on (even if that was the last one). */
function Session({ deck }: { deck: DeckDetail }) {
  const [reviewing, setReviewing] = useState<number | null>(null);
  const answer = useAnswer(deck.id);
  const shown = reviewing === null ? undefined : deck.items.find((i) => i.position === reviewing);

  if (shown) {
    return (
      <Frame deck={deck}>
        <ItemView item={shown} pending={false} onAnswer={() => undefined} />
        <Feedback
          item={shown}
          xp={XP_PER_CORRECT}
          last={Boolean(deck.completed_at)}
          onNext={() => setReviewing(null)}
        />
      </Frame>
    );
  }
  if (deck.completed_at) return <Summary deck={deck} />;
  if (!deck.started_at) return <Intro deck={deck} />;

  const next = deck.items.find((i) => !i.answered);
  if (!next) return null;
  const send = (response: ItemResponse) =>
    answer.mutate(
      { position: next.position, response },
      {
        onSuccess: () => {
          if (next.type !== "flashcard") setReviewing(next.position);
        },
        onError: (e) => toast.error(errorMessage(e)),
      },
    );
  return (
    <Frame deck={deck}>
      <AnimatePresence mode="wait">
        <Slide key={next.position}>
          <ItemView item={next} pending={answer.isPending} onAnswer={send} />
        </Slide>
      </AnimatePresence>
    </Frame>
  );
}

function Slide({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      exit={reduced ? { opacity: 0 } : { opacity: 0, x: -40 }}
      transition={{ duration: 0.2 }}
    >
      {children}
    </motion.div>
  );
}

/** Header with the clock and progress, around the current question. */
function Frame({ deck, children }: { deck: DeckDetail; children: React.ReactNode }) {
  const done = deck.items.filter((i) => i.answered).length;
  const total = deck.items.length;
  return (
    <section aria-labelledby="deck-heading" className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-3">
          <h1 id="deck-heading" className="text-xl font-bold">
            {deckTitle(deck)}
          </h1>
          {!deck.completed_at && deck.deadline && (
            <Countdown deckId={deck.id} deadline={deck.deadline} />
          )}
        </div>
        <ProgressBar
          value={(done / Math.max(1, total)) * 100}
          label={`Question ${Math.min(done + 1, total)} of ${total}`}
          tone="mustard"
          showLabel
        />
      </header>
      {children}
    </section>
  );
}

function secondsLeft(deadline: string): number {
  return Math.max(0, Math.ceil((new Date(deadline).getTime() - Date.now()) / 1000));
}

function Countdown({ deckId, deadline }: { deckId: number; deadline: string }) {
  const [left, setLeft] = useState(() => secondsLeft(deadline));
  const refresh = useRefreshDeck(deckId);
  const { mutate } = refresh;
  useEffect(() => {
    const timer = window.setInterval(() => setLeft(secondsLeft(deadline)), 250);
    return () => window.clearInterval(timer);
  }, [deadline]);
  useEffect(() => {
    if (left === 0) mutate(); // the server finishes the session once its time is up
  }, [left, mutate]);
  const minutes = Math.floor(left / 60);
  const seconds = String(left % 60).padStart(2, "0");
  return (
    <p
      className={cx(
        "flex min-h-9 items-center gap-1 rounded-full px-3 font-display text-lg font-extrabold tabular-nums",
        left <= 30 ? "bg-berry-soft text-berry" : "bg-sunken text-ink",
      )}
      aria-label={`${minutes} minutes ${seconds} seconds left`}
      role="timer"
    >
      {minutes}:{seconds}
    </p>
  );
}

function Intro({ deck }: { deck: DeckDetail }) {
  const tz = useTimezone();
  const start = useStartDeck(deck.id);
  const kinds = [...new Set(deck.items.map((i) => i.type))];
  return (
    <section aria-labelledby="deck-heading" className="flex flex-col gap-4">
      <h1 id="deck-heading" className="text-2xl font-bold">
        {deckTitle(deck)}
      </h1>
      <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-5">
        <p className="font-bold text-pine">{focusLine(deck.focus, tz)}</p>
        <p className="font-display text-2xl font-extrabold">{sessionLine(deck)}</p>
        <ul className="flex flex-wrap gap-2" aria-label="Question types">
          {kinds.map((k) => (
            <li key={k} className="rounded-full bg-sunken px-3 py-1 text-sm font-bold">
              {TYPE_LABELS[k]}
            </li>
          ))}
        </ul>
        <p className="text-sm text-ink-soft">
          {deck.state === "closed"
            ? "This day is over, so this session is practice and won't change your streak."
            : `The clock starts when you press Start. Each right answer is worth ${XP_PER_CORRECT} XP on the leaderboard, plus a bonus for finishing. Questions left when time runs out count as missed.`}
        </p>
        <Button
          className="self-start"
          pending={start.isPending}
          onClick={() => start.mutate(undefined, { onError: (e) => toast.error(errorMessage(e)) })}
        >
          Start
        </Button>
      </div>
    </section>
  );
}

function Summary({ deck }: { deck: DeckDetail }) {
  const celebrate = Boolean(deck.milestone);
  const total = deck.items.length;
  return (
    <section aria-labelledby="summary" className="flex flex-col gap-4">
      <div className="relative flex flex-col items-center gap-3 rounded-lg border border-line bg-surface p-5 text-center sm:flex-row sm:text-left">
        <div className="relative">
          <Mascot
            mood="good"
            moment={celebrate ? { kind: "celebrate", key: `deck-${deck.id}` } : null}
            size={120}
          />
          <Confetti show={celebrate} />
        </div>
        <div className="flex flex-col gap-1">
          <h1 id="summary" className="text-2xl font-bold">
            {deck.knew} of {total} correct · +{deck.xp} XP
          </h1>
          <p className="text-ink-soft" role="status">
            {deck.counted_for_streak
              ? `Counted for your streak: ${deck.streak} ${deck.streak === 1 ? "day" : "days"} in a row.${deck.milestone ? ` That's a ${deck.milestone}-day milestone.` : ""}`
              : "This one doesn't change your streak."}
          </p>
          {deck.knew < total && (
            <p className="text-sm text-ink-soft">
              The ones you missed come back in the next few sessions.
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <Link
          to="/pulse/quiz"
          className="inline-flex min-h-11 items-center rounded-md bg-pine px-4 font-bold text-on-pine"
        >
          See the leaderboard
        </Link>
      </div>
      <h2 className="text-lg font-bold">Your answers</h2>
      <ul className="flex flex-col gap-2">
        {deck.items.map((item) => (
          <ResultRow key={item.position} item={item} />
        ))}
      </ul>
    </section>
  );
}

function ResultRow({ item }: { item: DeckItem }) {
  const solution = (item.solution as Solution | null) ?? {};
  return (
    <li className="flex gap-3 rounded-md border border-line bg-surface p-3">
      <span
        className={cx(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
          item.correct ? "bg-pine-soft text-pine-strong" : "bg-mustard-soft text-mustard-ink",
        )}
      >
        {item.correct ? <Icon name="check" className="h-4 w-4" /> : "↻"}
        <span className="sr-only">
          {item.correct ? "Correct" : item.answered ? "Missed" : "Not answered"}
        </span>
      </span>
      <div className="flex min-w-0 flex-col gap-1">
        <p className="text-xs font-bold uppercase tracking-wide text-ink-soft">
          {TYPE_LABELS[item.type]} · {item.source}
        </p>
        <p className="font-bold">{item.prompt}</p>
        {item.type === "match" && solution.pairs ? (
          <ul className="text-sm text-ink-soft">
            {(item.terms ?? []).map((term, i) => (
              <li key={term}>
                <strong>{term}</strong>: {item.clues?.[solution.pairs?.[i] ?? -1]}
              </li>
            ))}
          </ul>
        ) : (
          <p className="whitespace-pre-line text-sm text-ink-soft">
            {solution.answer && solution.answer !== solution.explanation && (
              <>
                Answer: <strong className="text-ink">{solution.answer}</strong>.{" "}
              </>
            )}
            {solution.explanation ?? item.back}
          </p>
        )}
        {item.chapter_id && item.course_id && (
          <Link
            to={`/lms/courses/${item.course_id}/chapters/${item.chapter_id}`}
            className="self-start text-sm font-bold text-pine underline"
          >
            Review this in the chapter
          </Link>
        )}
      </div>
    </li>
  );
}

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { Confetti } from "@/components/Confetti";
import { Icon } from "@/components/Icon";
import { Mascot } from "@/components/mascot/Mascot";
import { Button, ProgressBar, QueryView, Skeleton, toast } from "@/components/ui";
import { useNumericParam } from "@/features/lms/useIds";
import { cx } from "@/lib/cx";
import { formatExact, useTimezone } from "@/lib/time";
import {
  checkKeys,
  useAnswerCard,
  useCheck,
  useStartCheck,
  type CardAnswer,
  type CheckCard,
  type CheckDetail,
} from "./api";
import { Countdown } from "./Countdown";
import { MatchCard } from "./MatchCard";
import { TimeLeft } from "./TimeLeft";

const KIND_LABEL: Record<CheckCard["kind"], string> = {
  choice: "Pick one",
  short: "Type the missing term",
  match: "Match",
};

export function CheckPage() {
  const query = useCheck(useNumericParam("checkId"));
  return (
    <div className="flex max-w-xl flex-col gap-4">
      <Breadcrumbs
        items={[
          { label: "Study checks", to: "/pulse/checks" },
          { label: query.data?.title ?? "Study check" },
        ]}
      />
      <QueryView
        query={query}
        skeleton={
          <div className="flex flex-col gap-3">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-72 w-full" />
          </div>
        }
      >
        {(check) => <CheckView check={check} />}
      </QueryView>
    </div>
  );
}

function CheckView({ check }: { check: CheckDetail }) {
  // The card just answered stays on screen (flipped) until the student moves on, even when that
  // answer finished the check.
  const [showing, setShowing] = useState<number | null>(null);
  const attempt = check.attempt;
  const inProgress = attempt !== null && !attempt.finished;
  if ((check.state === "open" && inProgress) || showing !== null)
    return <Player check={check} showing={showing} onShow={setShowing} />;
  if (check.state === "open" || check.state === "upcoming") return <Intro check={check} />;
  return <Result check={check} />;
}

function chapterLine(check: CheckDetail): string {
  return check.chapters.map((c) => `${c.course_code} Ch ${c.order}: ${c.title}`).join(" and ");
}

function Intro({ check }: { check: CheckDetail }) {
  const tz = useTimezone();
  const start = useStartCheck(check.id);
  const retry = check.attempt?.finished === true;
  return (
    <section aria-labelledby="check-heading" className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 id="check-heading" className="text-2xl font-bold">
          Study check
        </h1>
        <p className="font-bold text-pine">{chapterLine(check)}</p>
      </header>
      {check.state === "upcoming" ? (
        <p className="text-ink-soft">
          Opens {formatExact(check.opens_at, tz)}, the day your schedule has you on this chapter.
          Study it first, then come back.
        </p>
      ) : (
        <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-5">
          {retry ? (
            <p>
              You got {check.attempt?.correct} of {check.card_count} last time
              {check.attempt?.timed_out ? " before time ran out" : ""} and earned{" "}
              {check.attempt?.xp ?? 0} XP. You have one more try with new cards; get{" "}
              {check.pass_mark} right to keep your streak.
            </p>
          ) : (
            <p>
              {check.card_count} cards on what you studied: pick an answer, type a missing term, or
              match terms to sentences. Each card shows if you were right. Get {check.pass_mark} of{" "}
              {check.card_count} right to keep your streak.
            </p>
          )}
          <p className="text-sm text-ink-soft">
            You have 3 minutes once you press Start. Every right answer earns 10 XP, and answering
            them all earns 20 more.
          </p>
          <p className="text-sm">
            <TimeLeft closesAt={check.closes_at} /> ·{" "}
            <span className="text-ink-soft">closes {formatExact(check.closes_at, tz)}</span>
          </p>
          <Button
            className="self-start"
            onClick={() =>
              start.mutate(undefined, { onError: (e) => toast.error(errorMessage(e)) })
            }
            pending={start.isPending}
            pendingLabel="Getting your cards…"
          >
            {retry ? "Try again with new cards" : "Start"}
          </Button>
        </div>
      )}
      <ChapterLinks check={check} label="Review the chapter" />
    </section>
  );
}

function Player({
  check,
  showing,
  onShow,
}: {
  check: CheckDetail;
  showing: number | null;
  onShow: (position: number | null) => void;
}) {
  const answer = useAnswerCard(check.id);
  const client = useQueryClient();
  const refresh = useCallback(
    () => void client.invalidateQueries({ queryKey: checkKeys.detail(check.id) }),
    [client, check.id],
  );
  const cards = check.attempt?.cards ?? [];
  const next = cards.find((c) => c.result === null);
  const card = showing !== null ? cards[showing] : next;
  if (!card) return null;
  const answered = cards.filter((c) => c.result !== null).length;

  const send = (body: CardAnswer) =>
    answer.mutate(
      { position: card.position, ...body },
      {
        onSuccess: () => onShow(card.position),
        onError: (e) => {
          toast.error(errorMessage(e));
          refresh();
        },
      },
    );
  const running = check.attempt && !check.attempt.finished && check.attempt.expires_at;

  return (
    <section aria-labelledby="check-heading" className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <h1 id="check-heading" className="text-2xl font-bold">
          Study check
        </h1>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-sm">
            <TimeLeft closesAt={check.closes_at} />
            {check.attempt && check.attempt.number > 1 && (
              <span className="text-ink-soft"> · second try</span>
            )}
          </p>
          {running && check.attempt?.expires_at && (
            <Countdown expiresAt={check.attempt.expires_at} onExpire={refresh} />
          )}
        </div>
        <ProgressBar
          value={(answered / Math.max(1, cards.length)) * 100}
          label={`Card ${Math.min(card.position + 1, cards.length)} of ${cards.length}`}
          tone="mustard"
          showLabel
        />
      </header>
      <AnimatePresence mode="wait">
        {card.kind === "match" ? (
          <MatchCard
            key={`${check.attempt?.number}-${card.position}`}
            card={card}
            pending={answer.isPending}
            onAnswer={(pairs) => send({ pairs })}
          />
        ) : (
          <Flashcard
            key={`${check.attempt?.number}-${card.position}`}
            card={card}
            pending={answer.isPending}
            onAnswer={send}
          />
        )}
      </AnimatePresence>
      {card.result && (
        <Button className="self-end" onClick={() => onShow(null)}>
          {answered === cards.length ? "See how you did" : "Next card"}
        </Button>
      )}
    </section>
  );
}

function Flashcard({
  card,
  pending,
  onAnswer,
}: {
  card: CheckCard;
  pending: boolean;
  onAnswer: (body: CardAnswer) => void;
}) {
  const reduced = Boolean(useReducedMotion());
  const flipped = card.result !== null;
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      exit={reduced ? { opacity: 0 } : { opacity: 0, x: -40 }}
      transition={{ duration: 0.2 }}
      style={{ perspective: 1200 }}
    >
      <motion.div
        animate={{ rotateY: flipped && !reduced ? 180 : 0 }}
        transition={{ duration: reduced ? 0 : 0.4 }}
        className="relative grid min-h-72 w-full"
        style={{ transformStyle: "preserve-3d" }}
      >
        <Face side="front" hidden={flipped} reduced={reduced}>
          <span className="text-xs font-bold uppercase tracking-wide text-ink-soft">
            {KIND_LABEL[card.kind]} · {card.source}
          </span>
          <p className="font-display text-xl font-bold">{card.front}</p>
          {card.kind === "short" ? (
            <ShortAnswer disabled={flipped || pending} pending={pending} onAnswer={onAnswer} />
          ) : (
            <fieldset className="mt-auto flex flex-col gap-2" disabled={flipped || pending}>
              <legend className="sr-only">Choose an answer</legend>
              {card.options.map((option, i) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => onAnswer({ choice: i })}
                  className="min-h-11 rounded-md border border-line bg-paper px-3 py-2 text-left font-bold hover:border-pine focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink disabled:opacity-60"
                >
                  {option}
                </button>
              ))}
            </fieldset>
          )}
        </Face>
        <Face side="back" hidden={!flipped} reduced={reduced} tone={card.result?.correct}>
          {card.result && <Back card={card} />}
        </Face>
      </motion.div>
    </motion.div>
  );
}

function ShortAnswer({
  disabled,
  pending,
  onAnswer,
}: {
  disabled: boolean;
  pending: boolean;
  onAnswer: (body: CardAnswer) => void;
}) {
  const [text, setText] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (text.trim()) onAnswer({ text: text.trim() });
  };
  return (
    <form onSubmit={submit} className="mt-auto flex flex-col gap-2">
      <label htmlFor="short-answer" className="text-sm font-bold">
        Your answer
      </label>
      <input
        id="short-answer"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
        autoComplete="off"
        maxLength={120}
        className="min-h-11 rounded-md border border-line bg-paper px-3 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink"
      />
      <Button
        type="submit"
        className="self-start"
        pending={pending}
        disabled={disabled || !text.trim()}
      >
        Check
      </Button>
    </form>
  );
}

/** The right answer in words, whatever the card kind. */
function answerText(card: CheckCard): string {
  const result = card.result;
  if (!result) return "";
  if (card.kind === "short") return result.expected_text ?? "";
  if (card.kind === "match")
    return card.terms.map((t, i) => `${t}: ${card.clues[result.right_pairs?.[i] ?? 0]}`).join("; ");
  return result.answer === null ? "" : (card.options[result.answer] ?? "");
}

function Face({
  side,
  hidden,
  reduced,
  tone,
  children,
}: {
  side: "front" | "back";
  hidden: boolean;
  reduced: boolean;
  tone?: boolean;
  children: React.ReactNode;
}) {
  const back = side === "back";
  return (
    <div
      aria-hidden={hidden}
      className={cx(
        "col-start-1 row-start-1 flex flex-col gap-3 rounded-lg border p-6 shadow-sm",
        !back && "border-line bg-surface",
        back && (tone ? "border-pine bg-pine-soft" : "border-mustard bg-mustard-soft"),
        reduced && hidden && "invisible",
      )}
      style={{
        backfaceVisibility: "hidden",
        transform: back && !reduced ? "rotateY(180deg)" : undefined,
      }}
    >
      {children}
    </div>
  );
}

function Back({ card }: { card: CheckCard }) {
  const result = card.result;
  if (!result) return null;
  return (
    <>
      <p role="status" className="flex items-center gap-2 text-lg font-bold">
        {result.correct ? (
          <>
            <Icon name="check" className="h-5 w-5" /> Right
          </>
        ) : (
          "Not quite"
        )}
      </p>
      {card.kind === "short" && !result.correct && result.given_text && (
        <p>
          <span className="text-ink-soft">You wrote: </span>
          {result.given_text}
        </p>
      )}
      <p>
        <span className="text-ink-soft">Answer: </span>
        <span className="font-bold">{answerText(card)}</span>
      </p>
      <p>{result.explanation}</p>
      <blockquote className="mt-auto border-l-2 border-ink-faint pl-3 text-sm text-ink-soft">
        From the chapter: “{result.source_excerpt}”
      </blockquote>
    </>
  );
}

function Result({ check }: { check: CheckDetail }) {
  const celebrate = Boolean(check.milestone);
  const cards = check.attempt?.cards ?? [];
  const correct = check.attempt?.correct ?? 0;
  return (
    <section aria-labelledby="result" className="flex flex-col gap-4">
      <div className="relative flex flex-col items-center gap-3 rounded-lg border border-line bg-surface p-5 text-center sm:flex-row sm:text-left">
        <div className="relative">
          <Mascot
            mood={check.passed ? "good" : "medium"}
            moment={celebrate ? { kind: "celebrate", key: `check-${check.id}` } : null}
            size={120}
          />
          <Confetti show={celebrate} />
        </div>
        <div className="flex flex-col gap-1">
          <h1 id="result" className="text-2xl font-bold">
            {resultHeading(check, correct)}
          </h1>
          <p className="text-ink-soft" role="status">
            {resultLine(check)}
          </p>
          {check.attempt && (
            <p className="font-display text-lg font-extrabold text-mustard-ink">
              +{check.attempt.xp} XP
              {check.attempt.timed_out && (
                <span className="ml-2 font-body text-sm font-bold text-ink-soft">Time ran out</span>
              )}
            </p>
          )}
        </div>
      </div>
      {cards.length > 0 && (
        <ol className="flex flex-col gap-2">
          {cards.map((c) => (
            <li
              key={c.position}
              className="flex gap-3 rounded-md border border-line bg-surface p-3"
            >
              <span
                className={cx(
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
                  c.result?.correct
                    ? "bg-pine-soft text-pine-strong"
                    : "bg-mustard-soft text-mustard-ink",
                )}
              >
                {c.result?.correct ? <Icon name="check" className="h-4 w-4" /> : "×"}
                <span className="sr-only">{c.result?.correct ? "Right" : "Not right"}</span>
              </span>
              <div className="flex flex-col gap-1">
                <p className="font-bold">{c.kind === "match" ? "Matching" : c.front}</p>
                {c.result ? (
                  <p className="text-sm text-ink-soft">
                    Answer: {answerText(c)}.{c.kind === "match" ? "" : ` ${c.result.explanation}`}
                  </p>
                ) : (
                  <p className="text-sm text-ink-soft">Not answered before time ran out.</p>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
      <ChapterLinks check={check} label="Review this chapter" />
      <Link
        to="/pulse/checks"
        className="inline-flex min-h-11 items-center self-start rounded-md bg-pine px-4 font-bold text-on-pine"
      >
        Back to your streak
      </Link>
    </section>
  );
}

function resultHeading(check: CheckDetail, correct: number): string {
  if (check.state === "missed") return "This check closed";
  return `${correct} of ${check.card_count} right`;
}

function resultLine(check: CheckDetail): string {
  if (check.state === "missed") return "It closed before you took it, so it didn't count.";
  if (!check.passed) return "Not enough right on either try, so this one didn't count.";
  if (!check.counted_for_streak) return "Passed, but after the check closed, so it didn't count.";
  const streak = `${check.streak} ${check.streak === 1 ? "check" : "checks"} in a row`;
  return check.milestone ? `Passed. ${streak}: that's a milestone.` : `Passed. ${streak}.`;
}

function ChapterLinks({ check, label }: { check: CheckDetail; label: string }) {
  return (
    <ul className="flex flex-col gap-1">
      {check.chapters.map((c) => (
        <li key={c.id}>
          <Link
            to={`/lms/courses/${c.course_id}/chapters/${c.id}`}
            className="text-sm font-bold text-pine underline"
          >
            {label}: {c.course_code} Ch {c.order}
          </Link>
        </li>
      ))}
    </ul>
  );
}

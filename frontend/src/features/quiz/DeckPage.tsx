import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { Confetti } from "@/components/Confetti";
import { Icon } from "@/components/Icon";
import { Mascot } from "@/components/mascot/Mascot";
import { Button, ProgressBar, QueryView, Skeleton, toast } from "@/components/ui";
import { useNumericParam } from "@/features/lms/useIds";
import { cx } from "@/lib/cx";
import { useDeck, useReviewCard, useTodayDeck, type DeckCard, type DeckDetail } from "./api";
import { formatDeckDay, TOPIC_LABELS } from "./topics";

export function TodayDeckPage() {
  return <DeckView query={useTodayDeck()} />;
}

export function DeckPage() {
  return <DeckView query={useDeck(useNumericParam("deckId"))} />;
}

function DeckView({ query }: { query: ReturnType<typeof useTodayDeck> }) {
  return (
    <div className="flex max-w-xl flex-col gap-4">
      <Breadcrumbs
        items={[
          { label: "Quiz", to: "/pulse/quiz" },
          { label: query.data ? deckTitle(query.data) : "Flashcards" },
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
        {(deck) => (deck.completed_at ? <Summary deck={deck} /> : <Player deck={deck} />)}
      </QueryView>
    </div>
  );
}

function deckTitle(deck: DeckDetail): string {
  return `Flashcards for ${formatDeckDay(deck.day, { weekday: "long", month: "short", day: "numeric" })}`;
}

function Player({ deck }: { deck: DeckDetail }) {
  const review = useReviewCard(deck.id);
  const card = deck.cards.find((c) => c.knew === null);
  const done = deck.cards.filter((c) => c.knew !== null).length;
  if (!card) return null;

  const rate = (knew: boolean) =>
    review.mutate({ card_id: card.id, knew }, { onError: (e) => toast.error(errorMessage(e)) });

  return (
    <section aria-labelledby="deck-heading" className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <h1 id="deck-heading" className="text-2xl font-bold">
          {deckTitle(deck)}
        </h1>
        <p className="text-ink-soft">
          {deck.state === "closed"
            ? "This day is over, so this deck is practice and won't change your streak."
            : "Read the question, think of your answer, then flip the card and be honest with yourself."}
        </p>
        <ProgressBar
          value={(done / Math.max(1, deck.cards.length)) * 100}
          label={`Card ${done + 1} of ${deck.cards.length}`}
          tone="mustard"
          showLabel
        />
      </header>
      <AnimatePresence mode="wait">
        <CardStep key={card.id} card={card} pending={review.isPending} onRate={rate} />
      </AnimatePresence>
    </section>
  );
}

function CardStep({
  card,
  pending,
  onRate,
}: {
  card: DeckCard;
  pending: boolean;
  onRate: (knew: boolean) => void;
}) {
  const [flipped, setFlipped] = useState(false);
  return (
    <div className="flex flex-col gap-4">
      <Flashcard card={card} flipped={flipped} onFlip={() => setFlipped(true)} />
      {flipped ? (
        <div className="grid grid-cols-2 gap-3">
          <Button variant="secondary" disabled={pending} onClick={() => onRate(false)}>
            Still learning
          </Button>
          <Button pending={pending} onClick={() => onRate(true)}>
            Got it
          </Button>
        </div>
      ) : (
        <Button onClick={() => setFlipped(true)}>Show answer</Button>
      )}
    </div>
  );
}

function Flashcard({
  card,
  flipped,
  onFlip,
}: {
  card: DeckCard;
  flipped: boolean;
  onFlip: () => void;
}) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      exit={reduced ? { opacity: 0 } : { opacity: 0, x: -40 }}
      transition={{ duration: 0.2 }}
      style={{ perspective: 1200 }}
    >
      <motion.button
        type="button"
        onClick={onFlip}
        aria-label={flipped ? undefined : "Flip the card to see the answer"}
        disabled={flipped}
        animate={{ rotateY: flipped && !reduced ? 180 : 0 }}
        transition={{ duration: reduced ? 0 : 0.4 }}
        className="relative grid min-h-64 w-full rounded-lg text-left disabled:cursor-default"
        style={{ transformStyle: "preserve-3d" }}
      >
        <CardFace card={card} side="front" hidden={flipped} reduced={Boolean(reduced)} />
        <CardFace card={card} side="back" hidden={!flipped} reduced={Boolean(reduced)} />
      </motion.button>
    </motion.div>
  );
}

function CardFace({
  card,
  side,
  hidden,
  reduced,
}: {
  card: DeckCard;
  side: "front" | "back";
  hidden: boolean;
  reduced: boolean;
}) {
  const back = side === "back";
  return (
    <div
      aria-hidden={hidden}
      className={cx(
        "col-start-1 row-start-1 flex flex-col gap-3 rounded-lg border p-6 shadow-sm",
        back ? "border-pine bg-pine-soft" : "border-line bg-surface",
        reduced && hidden && "invisible",
      )}
      style={{
        backfaceVisibility: "hidden",
        transform: back && !reduced ? "rotateY(180deg)" : undefined,
      }}
    >
      <span className="text-xs font-bold uppercase tracking-wide text-ink-soft">
        {TOPIC_LABELS[card.topic]}
        {back ? " · Answer" : ""}
      </span>
      <p className={cx("font-display", back ? "text-lg" : "text-xl font-bold")}>
        {back ? card.back : card.front}
      </p>
      {!back && <span className="mt-auto text-sm text-ink-soft">Tap the card to flip it</span>}
    </div>
  );
}

function Summary({ deck }: { deck: DeckDetail }) {
  const celebrate = Boolean(deck.milestone);
  const total = deck.cards.length;
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
            Deck done · {deck.knew} of {total} known
          </h1>
          <p className="text-ink-soft" role="status">
            {deck.counted_for_streak
              ? `Counted for your streak: ${deck.streak} ${deck.streak === 1 ? "day" : "days"} in a row.${deck.milestone ? ` That's a ${deck.milestone}-day milestone.` : ""}`
              : "Practice run. It doesn't change your streak."}
          </p>
          {deck.knew < total && (
            <p className="text-sm text-ink-soft">
              Cards you're still learning come back in the next few decks.
            </p>
          )}
        </div>
      </div>
      <ul className="flex flex-col gap-2">
        {deck.cards.map((c) => (
          <li key={c.id} className="flex gap-3 rounded-md border border-line bg-surface p-3">
            <span
              className={cx(
                "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
                c.knew ? "bg-pine-soft text-pine-strong" : "bg-mustard-soft text-mustard-ink",
              )}
            >
              {c.knew ? <Icon name="check" className="h-4 w-4" /> : "↻"}
              <span className="sr-only">{c.knew ? "Got it" : "Still learning"}</span>
            </span>
            <div className="flex flex-col gap-1">
              <p className="font-bold">{c.front}</p>
              <p className="text-sm text-ink-soft">{c.back}</p>
            </div>
          </li>
        ))}
      </ul>
      <Link
        to="/pulse/quiz"
        className="inline-flex min-h-11 items-center self-start rounded-md bg-pine px-4 font-bold text-on-pine"
      >
        Back to your streak
      </Link>
    </section>
  );
}

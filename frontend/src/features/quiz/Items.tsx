import { motion, useReducedMotion } from "framer-motion";
import { useState, type FormEvent } from "react";
import { Button, Input } from "@/components/ui";
import { cx } from "@/lib/cx";
import type { DeckItem, ItemResponse, Solution } from "./api";
import { TYPE_LABELS } from "./topics";

type ItemProps = {
  item: DeckItem;
  pending: boolean;
  onAnswer: (response: ItemResponse) => void;
};

function solutionOf(item: DeckItem): Solution | null {
  return (item.solution as Solution | null) ?? null;
}

function responseOf<T extends ItemResponse>(item: DeckItem): Partial<T> {
  return (item.response as T | null) ?? {};
}

export function ItemView(props: ItemProps) {
  const { item } = props;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs font-bold uppercase tracking-wide text-ink-soft">
        {TYPE_LABELS[item.type]} · {item.source}
      </p>
      {item.type === "flashcard" && <FlashcardItem {...props} />}
      {item.type === "mcq" && <McqItem {...props} />}
      {item.type === "short" && <ShortItem {...props} />}
      {item.type === "match" && <MatchItem {...props} />}
    </div>
  );
}

function FlashcardItem({ item, pending, onAnswer }: ItemProps) {
  const [flipped, setFlipped] = useState(false);
  const reduced = useReducedMotion();
  return (
    <>
      <div style={{ perspective: 1200 }}>
        <motion.button
          type="button"
          onClick={() => setFlipped(true)}
          aria-label={flipped ? undefined : "Flip the card to see the answer"}
          disabled={flipped}
          animate={{ rotateY: flipped && !reduced ? 180 : 0 }}
          transition={{ duration: reduced ? 0 : 0.4 }}
          className="relative grid min-h-56 w-full rounded-lg text-left disabled:cursor-default"
          style={{ transformStyle: "preserve-3d" }}
        >
          <Face text={item.prompt} hidden={flipped} reduced={Boolean(reduced)} hint />
          <Face text={item.back ?? ""} hidden={!flipped} reduced={Boolean(reduced)} back />
        </motion.button>
      </div>
      {flipped ? (
        <div className="grid grid-cols-2 gap-3">
          <Button variant="secondary" disabled={pending} onClick={() => onAnswer({ knew: false })}>
            Still learning
          </Button>
          <Button pending={pending} onClick={() => onAnswer({ knew: true })}>
            Got it
          </Button>
        </div>
      ) : (
        <Button onClick={() => setFlipped(true)}>Show answer</Button>
      )}
    </>
  );
}

function Face({
  text,
  hidden,
  reduced,
  back = false,
  hint = false,
}: {
  text: string;
  hidden: boolean;
  reduced: boolean;
  back?: boolean;
  hint?: boolean;
}) {
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
      {back && (
        <span className="text-xs font-bold uppercase tracking-wide text-ink-soft">Answer</span>
      )}
      <p className={cx("whitespace-pre-line font-display", back ? "text-lg" : "text-xl font-bold")}>
        {text}
      </p>
      {hint && <span className="mt-auto text-sm text-ink-soft">Tap the card to flip it</span>}
    </div>
  );
}

function Prompt({ text }: { text: string }) {
  return (
    <p className="whitespace-pre-line rounded-lg border border-line bg-surface p-5 font-display text-xl font-bold">
      {text}
    </p>
  );
}

function McqItem({ item, pending, onAnswer }: ItemProps) {
  const solution = solutionOf(item);
  const chosen = responseOf<{ choice: number }>(item).choice;
  return (
    <>
      <Prompt text={item.prompt} />
      <ul className="flex flex-col gap-2" aria-label="Options">
        {(item.options ?? []).map((option, index) => {
          const right = solution?.choice === index;
          const wrong = item.answered && chosen === index && !right;
          return (
            <li key={option}>
              <button
                type="button"
                disabled={item.answered || pending}
                onClick={() => onAnswer({ choice: index })}
                className={cx(
                  "flex min-h-11 w-full items-start gap-3 rounded-md border px-4 py-3 text-left transition-colors",
                  right && "border-pine bg-pine-soft",
                  wrong && "border-berry bg-berry-soft",
                  !right && !wrong && "border-line bg-surface enabled:hover:border-ink-faint",
                )}
              >
                <span className="font-bold text-ink-soft">{"ABCD"[index]}</span>
                <span>{option}</span>
                {right && <span className="sr-only"> (correct answer)</span>}
                {wrong && <span className="sr-only"> (your answer)</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function ShortItem({ item, pending, onAnswer }: ItemProps) {
  const [text, setText] = useState(responseOf<{ text: string }>(item).text ?? "");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim()) onAnswer({ text: text.trim() });
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Prompt text={item.prompt} />
      <Input
        label="Your answer"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={item.answered}
        autoComplete="off"
        autoFocus
        maxLength={120}
      />
      {!item.answered && (
        <Button type="submit" pending={pending} disabled={!text.trim()}>
          Check
        </Button>
      )}
    </form>
  );
}

function MatchItem({ item, pending, onAnswer }: ItemProps) {
  const terms = item.terms ?? [];
  const clues = item.clues ?? [];
  const given = responseOf<{ pairs: number[] }>(item).pairs;
  const [pairs, setPairs] = useState<(number | null)[]>(given ?? terms.map(() => null));
  const [selected, setSelected] = useState<number | null>(null);
  const solution = solutionOf(item);
  const locked = item.answered || pending;

  const pickClue = (clue: number) => {
    if (locked) return;
    const owner = pairs.indexOf(clue);
    if (selected === null) {
      // tapping a matched sentence undoes that pair
      if (owner >= 0) setPairs(pairs.map((p, i) => (i === owner ? null : p)));
      return;
    }
    setPairs(pairs.map((p, i) => (i === selected ? clue : p === clue ? null : p)));
    setSelected(null);
  };

  const complete = pairs.every((p) => p !== null);
  return (
    <div className="flex flex-col gap-3">
      <p className="font-display text-xl font-bold">{item.prompt}</p>
      <p className="text-sm text-ink-soft">
        Tap a term, then the sentence it fills in. Tap a matched sentence to undo it.
      </p>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,12rem)_1fr]">
        <ul className="flex flex-col gap-2" aria-label="Terms">
          {terms.map((term, i) => (
            <li key={term}>
              <button
                type="button"
                disabled={locked}
                aria-pressed={selected === i}
                onClick={() => setSelected(selected === i ? null : i)}
                className={cx(
                  "flex min-h-11 w-full items-center gap-2 rounded-md border px-3 py-2 text-left font-bold",
                  selected === i ? "border-ink bg-ink text-paper" : "border-line bg-surface",
                )}
              >
                <Badge n={i} muted={pairs[i] === null} />
                {term}
              </button>
            </li>
          ))}
        </ul>
        <ul className="flex flex-col gap-2" aria-label="Sentences">
          {clues.map((clue, c) => {
            const owner = pairs.indexOf(c);
            const right = solution?.pairs ? solution.pairs[owner] === c : null;
            return (
              <li key={clue}>
                <button
                  type="button"
                  disabled={locked}
                  onClick={() => pickClue(c)}
                  className={cx(
                    "flex min-h-11 w-full items-start gap-2 rounded-md border px-3 py-2 text-left text-sm",
                    right === true && "border-pine bg-pine-soft",
                    right === false && "border-berry bg-berry-soft",
                    right === null && "border-line bg-surface",
                  )}
                >
                  {owner >= 0 ? <Badge n={owner} /> : <Badge n={null} />}
                  <span>
                    {clue}
                    {owner >= 0 && <span className="sr-only"> (matched with {terms[owner]})</span>}
                  </span>
                </button>
                {right === false && solution?.pairs && (
                  <p className="mt-1 text-sm text-ink-soft">
                    Answer: {terms[solution.pairs.indexOf(c)]}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </div>
      {!item.answered && (
        <Button
          pending={pending}
          disabled={!complete}
          onClick={() => onAnswer({ pairs: pairs as number[] })}
        >
          Check
        </Button>
      )}
    </div>
  );
}

const BADGE_COLORS = ["bg-mustard text-ink", "bg-pine text-on-pine", "bg-berry text-white"];

function Badge({ n, muted = false }: { n: number | null; muted?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold",
        n === null || muted ? "border border-dashed border-ink-faint" : BADGE_COLORS[n % 3],
      )}
    >
      {n === null ? "" : n + 1}
    </span>
  );
}

/** The banner after answering: right or wrong, the answer, and a way on. */
export function Feedback({
  item,
  xp,
  last,
  onNext,
}: {
  item: DeckItem;
  xp: number;
  last: boolean;
  onNext: () => void;
}) {
  const solution = solutionOf(item);
  const correct = Boolean(item.correct);
  return (
    <div
      role="status"
      className={cx(
        "flex flex-col gap-2 rounded-lg border p-4",
        correct ? "border-pine bg-pine-soft" : "border-berry bg-berry-soft",
      )}
    >
      <p className="font-display text-lg font-extrabold">
        {correct ? `Correct! +${xp} XP` : "Not quite"}
      </p>
      {item.type !== "match" && solution?.explanation && (
        <p className="whitespace-pre-line text-sm">
          {!correct && solution.answer && solution.answer !== solution.explanation && (
            <>
              Answer: <strong>{solution.answer}</strong>.{" "}
            </>
          )}
          {solution.explanation}
        </p>
      )}
      <Button autoFocus onClick={onNext} className="self-start">
        {last ? "See results" : "Continue"}
      </Button>
    </div>
  );
}

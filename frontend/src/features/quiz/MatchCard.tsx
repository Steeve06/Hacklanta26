import { useState } from "react";
import { Button } from "@/components/ui";
import { cx } from "@/lib/cx";
import type { CheckCard } from "./api";

/** Three key terms and the sentences they complete. Tap a term, then its sentence; tap a matched
 * sentence to undo it. After checking, each sentence shows whether its match was right.
 * Adapted from the daily-quiz matching question. */
export function MatchCard({
  card,
  pending,
  onAnswer,
}: {
  card: CheckCard;
  pending: boolean;
  onAnswer: (pairs: number[]) => void;
}) {
  const result = card.result;
  const [pairs, setPairs] = useState<(number | null)[]>(
    result?.pairs ?? card.terms.map(() => null),
  );
  const [selected, setSelected] = useState<number | null>(null);
  const locked = result !== null || pending;

  const pickClue = (clue: number) => {
    if (locked) return;
    const owner = pairs.indexOf(clue);
    if (selected === null) {
      if (owner >= 0) setPairs(pairs.map((p, i) => (i === owner ? null : p)));
      return;
    }
    setPairs(pairs.map((p, i) => (i === selected ? clue : p === clue ? null : p)));
    setSelected(null);
  };
  const complete = pairs.every((p) => p !== null);

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-6 shadow-sm">
      <span className="text-xs font-bold uppercase tracking-wide text-ink-soft">{card.source}</span>
      <p className="font-display text-xl font-bold">{card.front}</p>
      <p className="text-sm text-ink-soft">
        Tap a term, then the sentence it fills in. Tap a matched sentence to undo it.
      </p>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,11rem)_1fr]">
        <ul className="flex flex-col gap-2" aria-label="Terms">
          {card.terms.map((term, i) => (
            <li key={term}>
              <button
                type="button"
                disabled={locked}
                aria-pressed={selected === i}
                onClick={() => setSelected(selected === i ? null : i)}
                className={cx(
                  "flex min-h-11 w-full items-center gap-2 rounded-md border px-3 py-2 text-left font-bold",
                  selected === i ? "border-ink bg-ink text-paper" : "border-line bg-paper",
                )}
              >
                <Badge n={i} muted={pairs[i] === null} />
                {term}
              </button>
            </li>
          ))}
        </ul>
        <ul className="flex flex-col gap-2" aria-label="Sentences">
          {card.clues.map((clue, c) => {
            const owner = pairs.indexOf(c);
            const right = result?.right_pairs ? result.right_pairs[owner] === c : null;
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
                    right === null && "border-line bg-paper",
                  )}
                >
                  <Badge n={owner >= 0 ? owner : null} />
                  <span>
                    {clue}
                    {owner >= 0 && (
                      <span className="sr-only">
                        {" "}
                        (matched with {card.terms[owner]}
                        {right === true ? ", right" : right === false ? ", not right" : ""})
                      </span>
                    )}
                  </span>
                </button>
                {right === false && result?.right_pairs && (
                  <p className="mt-1 text-sm text-ink-soft">
                    Answer: {card.terms[result.right_pairs.indexOf(c)]}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </div>
      {result ? (
        <p role="status" className="font-bold">
          {result.correct ? "All three matched." : "Not all matched."}
        </p>
      ) : (
        <Button
          className="self-start"
          pending={pending}
          disabled={!complete}
          onClick={() => onAnswer(pairs as number[])}
        >
          Check
        </Button>
      )}
    </div>
  );
}

function Badge({ n, muted = false }: { n: number | null; muted?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold",
        n === null ? "border border-dashed border-ink-faint" : muted ? "bg-sunken" : "bg-mustard",
      )}
    >
      {n === null ? "" : n + 1}
    </span>
  );
}

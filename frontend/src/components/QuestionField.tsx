import { cx } from "@/lib/cx";

type Props = {
  index: number;
  prompt: string;
  options: string[];
  value: number | undefined;
  onChange?: (value: number) => void;
  disabled?: boolean;
  correctIndex?: number;
  explanation?: string;
  footer?: React.ReactNode;
};

export function QuestionField({
  index,
  prompt,
  options,
  value,
  onChange,
  disabled,
  correctIndex,
  explanation,
  footer,
}: Props) {
  const reviewed = correctIndex !== undefined;
  const name = `q-${index}`;
  return (
    <fieldset className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-4">
      <legend className="sr-only">Question {index + 1}</legend>
      <p className="font-bold" aria-hidden="true">
        <span className="mr-2 text-ink-soft">{index + 1}.</span>
        {prompt}
      </p>
      <p className="sr-only">{prompt}</p>
      <div className="flex flex-col gap-2">
        {options.map((option, i) => {
          const chosen = value === i;
          const isCorrect = reviewed && i === correctIndex;
          const isWrongChoice = reviewed && chosen && i !== correctIndex;
          return (
            <label
              key={option}
              className={cx(
                "flex min-h-11 cursor-pointer items-center gap-3 rounded-md border px-3 py-2",
                isCorrect && "border-pine bg-pine-soft",
                isWrongChoice && "border-berry bg-berry-soft",
                !reviewed && chosen && "border-ink",
                !reviewed && !chosen && "border-line hover:bg-sunken",
                reviewed && !isCorrect && !isWrongChoice && "border-line",
                disabled && "cursor-default",
              )}
            >
              <input
                type="radio"
                name={name}
                checked={chosen}
                disabled={disabled}
                onChange={() => onChange?.(i)}
                className="h-5 w-5 accent-[rgb(var(--pine))]"
              />
              <span className="flex-1">{option}</span>
              {isCorrect && (
                <span className="text-sm font-bold text-pine-strong">Correct answer</span>
              )}
              {isWrongChoice && <span className="text-sm font-bold text-berry">Your answer</span>}
            </label>
          );
        })}
      </div>
      {explanation && <p className="text-sm text-ink-soft">{explanation}</p>}
      {footer}
    </fieldset>
  );
}

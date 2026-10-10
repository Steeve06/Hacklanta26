import { useId, type ReactNode } from "react";

type FieldProps = {
  label: string;
  error?: string;
  hint?: string;
  children: (props: {
    id: string;
    "aria-invalid": boolean;
    "aria-describedby"?: string;
  }) => ReactNode;
};

export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  const describedBy =
    [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-bold text-ink">
        {label}
      </label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": describedBy })}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-xs text-ink-soft">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-xs font-bold text-berry">
          {error}
        </p>
      )}
    </div>
  );
}

export const inputClass =
  "min-h-11 w-full rounded-md border border-line bg-surface px-3 text-base text-ink placeholder:text-ink-faint aria-[invalid=true]:border-berry disabled:bg-sunken disabled:text-ink-soft";

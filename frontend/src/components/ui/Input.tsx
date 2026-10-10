import {
  forwardRef,
  type InputHTMLAttributes,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cx } from "@/lib/cx";
import { Field, inputClass } from "./Field";

type Common = { label: string; error?: string; hint?: string };

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & Common>(
  function Input({ label, error, hint, className, ...rest }, ref) {
    return (
      <Field label={label} error={error} hint={hint}>
        {(a11y) => <input ref={ref} className={cx(inputClass, className)} {...a11y} {...rest} />}
      </Field>
    );
  },
);

export function Select({
  label,
  error,
  hint,
  className,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & Common) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(a11y) => (
        <select className={cx(inputClass, "pr-8", className)} {...a11y} {...rest}>
          {children}
        </select>
      )}
    </Field>
  );
}

export function Textarea({
  label,
  error,
  hint,
  className,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & Common) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(a11y) => (
        <textarea className={cx(inputClass, "min-h-28 py-2", className)} {...a11y} {...rest} />
      )}
    </Field>
  );
}

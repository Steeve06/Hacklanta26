import { useId, useState, type InputHTMLAttributes } from "react";
import { Icon } from "@/components/Icon";
import { inputClass } from "@/components/ui/Field";
import { cx } from "@/lib/cx";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: string;
  error?: string;
  describedBy?: string;
};

export function PasswordInput({ label, error, describedBy, className, ...rest }: Props) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const errorId = `${id}-error`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-bold text-ink">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visible ? "text" : "password"}
          aria-invalid={Boolean(error)}
          aria-describedby={[error && errorId, describedBy].filter(Boolean).join(" ") || undefined}
          className={cx(inputClass, "pr-12", className)}
          {...rest}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          disabled={rest.disabled}
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 flex min-w-11 items-center justify-center rounded-r-md text-ink-soft hover:text-ink disabled:opacity-50"
        >
          <Icon name={visible ? "eyeOff" : "eye"} />
        </button>
      </div>
      {error && (
        <p id={errorId} className="text-xs font-bold text-berry">
          {error}
        </p>
      )}
    </div>
  );
}

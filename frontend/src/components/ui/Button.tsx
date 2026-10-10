import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import { useDelayed } from "@/lib/useDelayed";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "md" | "sm";

const variants: Record<Variant, string> = {
  primary: "bg-pine text-on-pine hover:bg-pine-strong disabled:bg-pine/50",
  secondary: "border border-line bg-surface text-ink hover:bg-sunken disabled:text-ink-faint",
  ghost: "text-ink-soft hover:bg-sunken hover:text-ink disabled:text-ink-faint",
  danger: "bg-berry text-white hover:bg-berry/90 disabled:bg-berry/50",
};

const sizes: Record<Size, string> = {
  md: "min-h-11 px-4 text-base",
  sm: "min-h-11 px-3 text-sm md:min-h-9",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  pending?: boolean;
  pendingLabel?: string;
  icon?: ReactNode;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    pending = false,
    pendingLabel,
    icon,
    className,
    children,
    disabled,
    type = "button",
    ...rest
  },
  ref,
) {
  const showSpinner = useDelayed(pending);
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      className={cx(
        "inline-flex select-none items-center justify-center gap-2 rounded-md font-bold transition-colors disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {showSpinner ? <Spinner /> : icon}
      <span>{pending && pendingLabel ? pendingLabel : children}</span>
    </button>
  );
});

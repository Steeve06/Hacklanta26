import { cx } from "@/lib/cx";

type Props = {
  value?: number;
  label: string;
  className?: string;
  tone?: "pine" | "mustard" | "berry";
  showLabel?: boolean;
};

const tones = { pine: "bg-pine", mustard: "bg-mustard", berry: "bg-berry" };

export function ProgressBar({ value, label, className, tone = "pine", showLabel = false }: Props) {
  const determinate = typeof value === "number";
  const pct = determinate ? Math.max(0, Math.min(100, value)) : 0;
  return (
    <div className={cx("flex flex-col gap-1", className)}>
      {showLabel && (
        <div className="flex justify-between text-xs text-ink-soft">
          <span>{label}</span>
          {determinate && <span>{Math.round(pct)}%</span>}
        </div>
      )}
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={determinate ? Math.round(pct) : undefined}
        className="h-2 w-full overflow-hidden rounded-full bg-sunken"
      >
        <div
          className={cx(
            "h-full rounded-full transition-[width] duration-500",
            tones[tone],
            !determinate && "w-1/3 animate-progress-indeterminate",
          )}
          style={determinate ? { width: `${pct}%` } : undefined}
        />
      </div>
    </div>
  );
}

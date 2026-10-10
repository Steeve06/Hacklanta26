import { MascotStill } from "@/components/mascot/MascotStill";
import { Button, ProgressBar } from "@/components/ui";
import { cx } from "@/lib/cx";
import type { PlanJob } from "./api";

const STAGES = ["Collecting courses", "Estimating work", "Building schedule", "Done"];

export function PlanProgress({
  job,
  onCancel,
  cancelling,
}: {
  job: PlanJob;
  onCancel: () => void;
  cancelling: boolean;
}) {
  const current = STAGES.indexOf(job.stage_label);
  return (
    <section
      aria-labelledby="plan-progress"
      className="flex flex-col items-start gap-4 rounded-lg border border-line bg-surface p-5"
    >
      <MascotStill mood="good" size={72} className="motion-safe:animate-bounce" />
      <h2 id="plan-progress" className="text-xl font-bold">
        Building your schedule
      </h2>
      <ProgressBar value={job.progress} label="Schedule progress" showLabel className="w-full" />
      <ol className="flex flex-col gap-1 text-sm" aria-live="polite">
        {STAGES.map((stage, i) => (
          <li
            key={stage}
            className={cx(
              "flex items-center gap-2",
              i < current && "text-pine-strong",
              i === current && "font-bold text-ink",
              i > current && "text-ink-faint",
            )}
          >
            <span
              aria-hidden="true"
              className={cx(
                "h-2.5 w-2.5 rounded-full border-2",
                i < current ? "border-pine bg-pine" : i === current ? "border-ink" : "border-line",
              )}
            />
            {stage}
            <span className="sr-only">
              {i < current ? "(finished)" : i === current ? "(in progress)" : ""}
            </span>
          </li>
        ))}
      </ol>
      <Button
        variant="ghost"
        size="sm"
        onClick={onCancel}
        pending={cancelling}
        pendingLabel="Cancelling…"
      >
        Cancel
      </Button>
    </section>
  );
}

import { useState } from "react";
import { toast } from "@/components/ui";
import type { AvailabilityBlock } from "@/features/pulse/api";
import { AvailabilityEditor } from "@/features/pulse/AvailabilityEditor";
import { AvailabilityGrid } from "@/features/pulse/AvailabilityGrid";
import { formatHours, LOW_WEEKLY_HOURS, totalHours } from "@/features/pulse/availability";
import { BlackoutsEditor } from "@/features/pulse/BlackoutsEditor";
import type { StepProps } from "../stepTypes";
import { StepFooter } from "../StepFooter";

export function AvailabilityStep({ state, saving, submit, goTo, error }: StepProps) {
  const [blocks, setBlocks] = useState<AvailabilityBlock[]>(state.availability.blocks);
  const hours = totalHours(blocks);
  return (
    <section aria-label="Weekly study time" className="flex flex-col gap-4">
      <p className="text-ink-soft">
        Mark the hours that are usually free each week. Pulse only schedules inside them.
      </p>
      <AvailabilityGrid value={blocks} onChange={setBlocks} />
      <p aria-live="polite" className="flex flex-wrap items-baseline gap-x-2 text-sm">
        <span className="font-bold">{formatHours(hours)} hours a week</span>
        {blocks.length > 0 && hours < LOW_WEEKLY_HOURS && (
          <span className="text-mustard-ink">
            That's under {LOW_WEEKLY_HOURS} hours. Pulse will plan it, but deadlines may not fit.
          </span>
        )}
      </p>
      <details className="rounded-lg border border-line bg-surface p-4">
        <summary className="min-h-11 cursor-pointer py-2 font-bold">Enter exact times</summary>
        <div className="pt-2">
          <AvailabilityEditor
            value={blocks}
            onChange={setBlocks}
            onMerged={(n) => toast.info(`Merged ${n} overlapping block${n === 1 ? "" : "s"}.`)}
          />
        </div>
      </details>
      <details className="rounded-lg border border-line bg-surface p-4">
        <summary className="min-h-11 cursor-pointer py-2 font-bold">
          Block off specific dates (optional)
        </summary>
        <p className="pb-2 text-sm text-ink-soft">
          Work shifts, trips, anything that isn't part of a normal week. These save right away.
        </p>
        <BlackoutsEditor />
      </details>
      <StepFooter
        onBack={() => goTo(1)}
        onNext={() => submit({ blocks })}
        nextDisabled={blocks.length === 0}
        hint={blocks.length === 0 ? "Add at least one block to continue." : undefined}
        saving={saving}
        error={error}
      />
    </section>
  );
}

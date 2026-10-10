import { Button } from "@/components/ui";
import { formatHours, shortTime, totalHours, WEEKDAYS } from "@/features/pulse/availability";
import type { AvailabilityBlock } from "@/features/pulse/api";
import { SASS_LEVELS } from "@/features/pulse/preferences";
import type { OnboardingState } from "../api";
import { limitingChoice, plannableHours } from "./weeklyCapacity";

function daysWithTime(blocks: AvailabilityBlock[]): string {
  const days = [...new Set(blocks.map((b) => b.weekday))].sort((a, b) => a - b);
  if (days.length === 7) return "every day";
  return days.map((d) => WEEKDAYS[d]?.slice(0, 3)).join(", ");
}

export function YourChoices({
  state,
  goTo,
  disabled,
}: {
  state: OnboardingState;
  goTo: (step: number) => void;
  disabled: boolean;
}) {
  const { preferences: p, notifications: n, availability } = state;
  const sass = SASS_LEVELS.find((s) => s.level === n.sass_level)?.name ?? "";
  const rows = [
    {
      step: 2,
      label: "Free time",
      value: `${formatHours(totalHours(availability.blocks))} hours a week (${daysWithTime(availability.blocks)})`,
    },
    { step: 3, label: "Weekly limit", value: `${formatHours(Number(p.max_hours_per_week))} hours` },
    {
      step: 3,
      label: "Most in one day",
      value: `${formatHours(Number(p.max_hours_per_day))} hours`,
    },
    { step: 3, label: "Session length", value: `${p.session_minutes} minutes` },
    {
      step: 3,
      label: "Study window",
      value: `${shortTime(p.earliest_time)} to ${shortTime(p.latest_time)} (${p.timezone})`,
    },
    {
      step: 4,
      label: "Reminders",
      value: `${sass}, quiet ${shortTime(n.quiet_start)} to ${shortTime(n.quiet_end)}`,
    },
  ];
  return (
    <section
      aria-labelledby="your-choices"
      className="rounded-lg border border-line bg-surface p-4"
    >
      <h2 id="your-choices" className="font-bold">
        Your choices
      </h2>
      <p className="mb-3 text-sm text-ink-soft">
        Pulse can plan up to {formatHours(plannableHours(state))} hours a week. The cap right now is{" "}
        {limitingChoice(state)}.
      </p>
      <dl className="flex flex-col divide-y divide-line">
        {rows.map((row) => (
          <div key={row.label} className="flex flex-wrap items-center gap-x-3 py-2">
            <dt className="w-36 shrink-0 text-sm text-ink-soft">{row.label}</dt>
            <dd className="min-w-0 flex-1 text-sm font-bold">{row.value}</dd>
            <dd>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => goTo(row.step)}
                disabled={disabled}
                aria-label={`Change ${row.label.toLowerCase()}`}
              >
                Change
              </Button>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

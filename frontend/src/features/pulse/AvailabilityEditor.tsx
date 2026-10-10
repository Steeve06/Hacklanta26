import { useState } from "react";
import { Button } from "@/components/ui";
import type { AvailabilityBlock } from "./api";
import { overlaps, shortTime, WEEKDAYS } from "./availability";

const TIMES = Array.from(
  { length: 48 },
  (_, i) => `${String(Math.floor(i / 2)).padStart(2, "0")}:${i % 2 ? "30" : "00"}`,
);

function label(t: string): string {
  const [h, m] = t.split(":").map(Number);
  const hour = (h ?? 0) % 12 || 12;
  return `${hour}:${String(m ?? 0).padStart(2, "0")} ${(h ?? 0) < 12 ? "am" : "pm"}`;
}

export function AvailabilityEditor({
  value,
  onChange,
}: {
  value: AvailabilityBlock[];
  onChange: (blocks: AvailabilityBlock[]) => void;
}) {
  return (
    <div className="flex flex-col divide-y divide-line rounded-lg border border-line bg-surface">
      {WEEKDAYS.map((name, weekday) => (
        <DayRow
          key={name}
          name={name}
          weekday={weekday}
          blocks={value.filter((b) => b.weekday === weekday)}
          onAdd={(block) => onChange([...value, block])}
          onRemove={(block) => onChange(value.filter((b) => b !== block))}
          all={value}
        />
      ))}
    </div>
  );
}

function DayRow({
  name,
  weekday,
  blocks,
  onAdd,
  onRemove,
  all,
}: {
  name: string;
  weekday: number;
  blocks: AvailabilityBlock[];
  onAdd: (b: AvailabilityBlock) => void;
  onRemove: (b: AvailabilityBlock) => void;
  all: AvailabilityBlock[];
}) {
  const [adding, setAdding] = useState(false);
  const [start, setStart] = useState("18:00");
  const [end, setEnd] = useState("20:00");
  const candidate = { weekday, start_time: `${start}:00`, end_time: `${end}:00` };
  const error =
    end <= start
      ? "End must be after start."
      : overlaps(all, candidate)
        ? "Overlaps another block."
        : undefined;
  return (
    <div className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start">
      <p className="w-28 shrink-0 pt-2 font-bold">{name}</p>
      <div className="flex flex-1 flex-col gap-2">
        <ul className="flex flex-wrap gap-2" aria-label={`${name} study blocks`}>
          {blocks.length === 0 && !adding && (
            <li className="pt-2 text-sm text-ink-soft">No study time</li>
          )}
          {[...blocks]
            .sort((a, b) => a.start_time.localeCompare(b.start_time))
            .map((b) => (
              <li
                key={`${b.start_time}-${b.end_time}`}
                className="flex min-h-11 items-center gap-1 rounded-full border border-pine bg-pine-soft pl-3 text-sm font-bold text-pine-strong"
              >
                {label(shortTime(b.start_time))}–{label(shortTime(b.end_time))}
                <button
                  type="button"
                  onClick={() => onRemove(b)}
                  aria-label={`Remove ${name} ${label(shortTime(b.start_time))} to ${label(shortTime(b.end_time))}`}
                  className="flex min-h-11 min-w-11 items-center justify-center rounded-full hover:bg-pine/10"
                >
                  ×
                </button>
              </li>
            ))}
        </ul>
        {adding ? (
          <div className="flex flex-wrap items-end gap-2">
            <TimeSelect label="From" value={start} onChange={setStart} />
            <TimeSelect label="To" value={end} onChange={setEnd} />
            <Button
              size="sm"
              disabled={Boolean(error)}
              onClick={() => {
                onAdd(candidate);
                setAdding(false);
              }}
            >
              Add
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setAdding(false)}>
              Cancel
            </Button>
            {error && <p className="w-full text-xs font-bold text-berry">{error}</p>}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="min-h-11 self-start text-sm font-bold text-pine underline"
          >
            Add time on {name}
          </button>
        )}
      </div>
    </div>
  );
}

function TimeSelect({
  label: text,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs font-bold">
      {text}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-11 rounded-md border border-line bg-surface px-2 text-base font-normal"
      >
        {TIMES.map((t) => (
          <option key={t} value={t}>
            {label(t)}
          </option>
        ))}
        <option value="23:59">11:59 pm</option>
      </select>
    </label>
  );
}

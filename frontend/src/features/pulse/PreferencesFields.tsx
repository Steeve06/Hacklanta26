import { Input, Select } from "@/components/ui";
import { cx } from "@/lib/cx";
import { preferenceErrors, type Preferences } from "./preferences";

function timezones(): string[] {
  try {
    return Intl.supportedValuesOf("timeZone");
  } catch {
    return [Intl.DateTimeFormat().resolvedOptions().timeZone];
  }
}

export function PreferencesFields({
  value,
  onChange,
  timezoneHint = "Detected from your device. Change it if you're travelling.",
  freeHours,
  disabled = false,
}: {
  value: Preferences;
  onChange: (p: Preferences) => void;
  timezoneHint?: string;
  /** Weekly free time the student marked, shown next to the weekly limit. */
  freeHours?: number;
  disabled?: boolean;
}) {
  const weekHint =
    freeHours === undefined
      ? "Leon never plans more than this in a week."
      : `Leon never plans more than this in a week. You marked ${freeHours.toFixed(1).replace(".0", "")} free hours.`;
  const errors = preferenceErrors(value);
  const set = <K extends keyof Preferences>(key: K, v: Preferences[K]) =>
    onChange({ ...value, [key]: v });
  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Study hours per week"
          type="number"
          min={2}
          max={40}
          step={0.5}
          disabled={disabled}
          value={value.max_hours_per_week}
          onChange={(e) => set("max_hours_per_week", e.target.value)}
          hint={weekHint}
          error={errors.max_hours_per_week}
        />
        <Input
          label="Most study hours in one day"
          type="number"
          min={1}
          max={12}
          step={0.5}
          disabled={disabled}
          value={value.max_hours_per_day}
          onChange={(e) => set("max_hours_per_day", e.target.value)}
          error={errors.max_hours_per_day}
        />
        <Select
          label="Time zone"
          value={value.timezone}
          onChange={(e) => set("timezone", e.target.value)}
          hint={timezoneHint}
          disabled={disabled}
        >
          {timezones().map((tz) => (
            <option key={tz} value={tz}>
              {tz.replaceAll("_", " ")}
            </option>
          ))}
        </Select>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Earliest study time"
          type="time"
          value={value.earliest_time.slice(0, 5)}
          onChange={(e) => set("earliest_time", e.target.value)}
          disabled={disabled}
        />
        <Input
          label="Latest study time"
          type="time"
          value={value.latest_time.slice(0, 5)}
          onChange={(e) => set("latest_time", e.target.value)}
          disabled={disabled}
          error={errors.latest_time}
        />
      </div>
      <fieldset>
        <legend className="mb-2 text-sm font-bold">Session length</legend>
        <div className="flex flex-wrap gap-2">
          {[25, 50, 90].map((m) => (
            <label
              key={m}
              className={cx(
                "flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-4 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ink",
                value.session_minutes === m
                  ? "border-ink bg-ink text-paper"
                  : "border-line bg-surface",
              )}
            >
              <input
                type="radio"
                name="session"
                className="sr-only"
                checked={value.session_minutes === m}
                disabled={disabled}
                onChange={() => set("session_minutes", m)}
              />
              {m} minutes
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  );
}

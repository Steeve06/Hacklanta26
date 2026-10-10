import { Input, Select } from "@/components/ui";
import { cx } from "@/lib/cx";
import { preferenceErrors, SASS_LEVELS } from "./preferences";

export type Preferences = {
  max_hours_per_day: string;
  session_minutes: number;
  earliest_time: string;
  latest_time: string;
  timezone: string;
  sass_level: number;
};

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
}: {
  value: Preferences;
  onChange: (p: Preferences) => void;
}) {
  const errors = preferenceErrors(value);
  const set = <K extends keyof Preferences>(key: K, v: Preferences[K]) =>
    onChange({ ...value, [key]: v });
  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Most study hours in one day"
          type="number"
          min={0.5}
          max={12}
          step={0.5}
          value={value.max_hours_per_day}
          onChange={(e) => set("max_hours_per_day", e.target.value)}
          error={errors.max_hours_per_day}
        />
        <Select
          label="Time zone"
          value={value.timezone}
          onChange={(e) => set("timezone", e.target.value)}
          hint="Detected from your device. Change it if you're travelling."
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
        />
        <Input
          label="Latest study time"
          type="time"
          value={value.latest_time.slice(0, 5)}
          onChange={(e) => set("latest_time", e.target.value)}
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
                "flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-4",
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
                onChange={() => set("session_minutes", m)}
              />
              {m} minutes
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-1 text-sm font-bold">How should reminders sound?</legend>
        <p className="mb-2 text-xs text-ink-soft">You can tone it down from any notification.</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {SASS_LEVELS.map((s) => (
            <label
              key={s.level}
              className={cx(
                "flex cursor-pointer flex-col gap-1 rounded-md border p-3",
                value.sass_level === s.level
                  ? "border-pine bg-pine-soft"
                  : "border-line bg-surface",
              )}
            >
              <span className="flex items-center gap-2 font-bold">
                <input
                  type="radio"
                  name="sass"
                  checked={value.sass_level === s.level}
                  onChange={() => set("sass_level", s.level)}
                  className="h-4 w-4 accent-[rgb(var(--pine))]"
                />
                {s.level}. {s.name}
              </span>
              <span className="text-sm italic text-ink-soft">“{s.sample}”</span>
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  );
}

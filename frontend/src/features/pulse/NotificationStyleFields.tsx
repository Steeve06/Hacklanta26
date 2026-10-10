import { MascotStill } from "@/components/mascot/MascotStill";
import type { MascotPose } from "@/components/mascot/types";

const SASS_POSE: Record<number, MascotPose> = {
  1: "calm",
  2: "nudge",
  3: "disappointed",
  4: "voice-note",
};
import { Input } from "@/components/ui";
import { cx } from "@/lib/cx";
import { SASS_LEVELS, styleErrors, type NotificationStyle } from "./preferences";

/** Sass level with a live sample of how reminders will read, and quiet hours. Used in
 * onboarding and Settings. */
export function NotificationStyleFields({
  value,
  onChange,
  disabled = false,
}: {
  value: NotificationStyle;
  onChange: (v: NotificationStyle) => void;
  disabled?: boolean;
}) {
  const errors = styleErrors(value);
  const selected = SASS_LEVELS.find((s) => s.level === value.sass_level) ?? SASS_LEVELS[1];
  const set = <K extends keyof NotificationStyle>(key: K, v: NotificationStyle[K]) =>
    onChange({ ...value, [key]: v });
  return (
    <div className="flex flex-col gap-5">
      <fieldset>
        <legend className="mb-2 text-sm font-bold">How should reminders sound?</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {SASS_LEVELS.map((s) => (
            <label
              key={s.level}
              className={cx(
                "flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-3 py-2 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ink",
                value.sass_level === s.level
                  ? "border-pine bg-pine-soft font-bold"
                  : "border-line bg-surface",
              )}
            >
              <input
                type="radio"
                name="sass"
                checked={value.sass_level === s.level}
                disabled={disabled}
                onChange={() => set("sass_level", s.level)}
                className="h-4 w-4 accent-[rgb(var(--pine))]"
              />
              {s.level}. {s.name}
            </label>
          ))}
        </div>
      </fieldset>
      {selected && (
        <figure className="flex items-start gap-3" aria-live="polite">
          <MascotStill pose={SASS_POSE[value.sass_level] ?? "calm"} size={56} />
          <blockquote className="rounded-lg rounded-tl-none border border-line bg-surface px-4 py-3">
            <p>{selected.sample}</p>
            <figcaption className="mt-1 text-xs text-ink-soft">
              A reminder at level {selected.level}. You can tone it down from any notification.
            </figcaption>
          </blockquote>
        </figure>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <Input
          label="Quiet hours start"
          type="time"
          value={value.quiet_start.slice(0, 5)}
          onChange={(e) => set("quiet_start", e.target.value)}
          disabled={disabled}
          hint="No push or email reminders from this time."
        />
        <Input
          label="Quiet hours end"
          type="time"
          value={value.quiet_end.slice(0, 5)}
          onChange={(e) => set("quiet_end", e.target.value)}
          disabled={disabled}
          error={errors.quiet_end}
        />
      </div>
    </div>
  );
}

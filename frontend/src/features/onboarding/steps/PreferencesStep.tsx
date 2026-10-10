import { useState } from "react";
import { totalHours } from "@/features/pulse/availability";
import { PreferencesFields } from "@/features/pulse/PreferencesFields";
import { detectTimezone, preferenceErrors, type Preferences } from "@/features/pulse/preferences";
import type { StepProps } from "../stepTypes";
import { StepFooter } from "../StepFooter";

export function PreferencesStep({ state, saving, submit, goTo, error }: StepProps) {
  const saved = state.preferences;
  const firstVisit = !state.completed_steps.includes(3);
  const detected = detectTimezone();
  const [prefs, setPrefs] = useState<Preferences>({
    max_hours_per_day: String(saved.max_hours_per_day),
    max_hours_per_week: String(saved.max_hours_per_week),
    session_minutes: saved.session_minutes,
    earliest_time: saved.earliest_time.slice(0, 5),
    latest_time: saved.latest_time.slice(0, 5),
    timezone: firstVisit && detected ? detected : saved.timezone,
  });
  const invalid = Object.keys(preferenceErrors(prefs)).length > 0;
  const hint =
    firstVisit && !detected
      ? `We couldn't detect your time zone, so it's set to ${saved.timezone.replaceAll("_", " ")}. Check it's right.`
      : undefined;
  return (
    <section aria-label="Study preferences" className="flex flex-col gap-4">
      <PreferencesFields
        value={prefs}
        onChange={setPrefs}
        timezoneHint={hint}
        freeHours={totalHours(state.availability.blocks)}
        disabled={saving}
      />
      <StepFooter
        onBack={() => goTo(2)}
        onNext={() => submit({ ...prefs })}
        nextDisabled={invalid}
        saving={saving}
        error={error}
      />
    </section>
  );
}

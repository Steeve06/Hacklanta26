import type { Preferences } from "./PreferencesFields";

export const SASS_LEVELS = [
  { level: 1, name: "Gentle", sample: "Your essay is due in 3 days. You've got this." },
  { level: 2, name: "Nudgy", sample: "Your essay is due in 3 days. Just saying." },
  {
    level: 3,
    name: "Dramatic",
    sample: "Your essay is due in 3 days. You have a plan, right? …Right?",
  },
  {
    level: 4,
    name: "Unhinged",
    sample: "3 days. THREE. I've cleared my schedule to stare at you.",
  },
];

export function preferenceErrors(p: Preferences): Partial<Record<keyof Preferences, string>> {
  const errors: Partial<Record<keyof Preferences, string>> = {};
  const hours = Number(p.max_hours_per_day);
  if (!(hours >= 0.5 && hours <= 12)) errors.max_hours_per_day = "Choose between 0.5 and 12 hours.";
  if (p.earliest_time >= p.latest_time) errors.latest_time = "Latest must be after earliest.";
  return errors;
}

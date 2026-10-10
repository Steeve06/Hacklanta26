export type Preferences = {
  max_hours_per_day: string;
  max_hours_per_week: string;
  session_minutes: number;
  earliest_time: string;
  latest_time: string;
  timezone: string;
};

export type NotificationStyle = {
  sass_level: number;
  quiet_start: string;
  quiet_end: string;
};

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

export const DEFAULT_SASS = 2;

export function preferenceErrors(p: Preferences): Partial<Record<keyof Preferences, string>> {
  const errors: Partial<Record<keyof Preferences, string>> = {};
  const hours = Number(p.max_hours_per_day);
  if (!(hours >= 1 && hours <= 12)) errors.max_hours_per_day = "Choose between 1 and 12 hours.";
  const week = Number(p.max_hours_per_week);
  if (!(week >= 2 && week <= 40)) errors.max_hours_per_week = "Choose between 2 and 40 hours.";
  if (p.earliest_time.slice(0, 5) >= p.latest_time.slice(0, 5))
    errors.latest_time = "Latest must be after earliest.";
  return errors;
}

export function styleErrors(
  s: NotificationStyle,
): Partial<Record<keyof NotificationStyle, string>> {
  return s.quiet_start.slice(0, 5) === s.quiet_end.slice(0, 5)
    ? { quiet_end: "Quiet hours need a different start and end." }
    : {};
}

/** The browser's time zone, or null when it can't be detected. */
export function detectTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

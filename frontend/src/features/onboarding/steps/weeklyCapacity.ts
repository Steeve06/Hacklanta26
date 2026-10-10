import { shortTime, totalHours } from "@/features/pulse/availability";
import type { OnboardingState } from "../api";

function toMinutes(t: string, isEnd = false): number {
  const [h = 0, m = 0] = shortTime(t).split(":").map(Number);
  const value = h * 60 + m;
  return isEnd && value === 0 ? 24 * 60 : value;
}

/** Hours Pulse can actually use in a week: free time inside the study window, at most the
 * daily maximum per day, and at most the weekly limit overall. */
export function plannableHours(state: OnboardingState): number {
  const { preferences: p, availability } = state;
  const from = toMinutes(p.earliest_time);
  const to = toMinutes(p.latest_time, true);
  const perDay = new Array<number>(7).fill(0);
  for (const b of availability.blocks) {
    const start = Math.max(from, toMinutes(b.start_time));
    const end = Math.min(to, toMinutes(b.end_time, true));
    perDay[b.weekday] = (perDay[b.weekday] ?? 0) + Math.max(0, end - start);
  }
  const dailyCap = Number(p.max_hours_per_day) * 60;
  const weekly = perDay.reduce((sum, m) => sum + Math.min(m, dailyCap), 0) / 60;
  return Math.min(weekly, Number(p.max_hours_per_week));
}

export function limitingChoice(state: OnboardingState): string {
  const free = totalHours(state.availability.blocks);
  const weekly = Number(state.preferences.max_hours_per_week);
  const usable = plannableHours(state);
  if (usable >= weekly - 0.05) return "your weekly limit";
  if (usable < free - 0.05) return "your daily maximum and study window";
  return "your free time";
}

import type { AvailabilityBlock } from "./api";

export function shortTime(t: string): string {
  return t.slice(0, 5);
}

export const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export function totalHours(blocks: AvailabilityBlock[]): number {
  return blocks.reduce((sum, b) => {
    const [sh = 0, sm = 0] = shortTime(b.start_time).split(":").map(Number);
    const [eh = 0, em = 0] = shortTime(b.end_time).split(":").map(Number);
    return sum + (eh * 60 + em - (sh * 60 + sm)) / 60;
  }, 0);
}

export function overlaps(blocks: AvailabilityBlock[], candidate: AvailabilityBlock): boolean {
  return blocks.some(
    (b) =>
      b.weekday === candidate.weekday &&
      shortTime(candidate.start_time) < shortTime(b.end_time) &&
      shortTime(b.start_time) < shortTime(candidate.end_time),
  );
}

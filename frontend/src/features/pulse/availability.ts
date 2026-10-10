import type { AvailabilityBlock } from "./api";

export const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export const SLOTS_PER_DAY = 48;
export const LOW_WEEKLY_HOURS = 5;

export function shortTime(t: string): string {
  return t.slice(0, 5);
}

function minutes(t: string): number {
  const [h = 0, m = 0] = shortTime(t).split(":").map(Number);
  return h * 60 + m;
}

/** End of a block in minutes; 00:00 as an end means midnight at the end of the day. */
function endMinutes(t: string): number {
  return shortTime(t) === "00:00" ? 24 * 60 : minutes(t);
}

function clock(totalMinutes: number): string {
  const m = totalMinutes % (24 * 60);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}:00`;
}

export function blockMinutes(b: AvailabilityBlock): number {
  return endMinutes(b.end_time) - minutes(b.start_time);
}

export function totalHours(blocks: AvailabilityBlock[]): number {
  return blocks.reduce((sum, b) => sum + Math.max(0, blockMinutes(b)) / 60, 0);
}

export function formatHours(hours: number): string {
  return hours.toFixed(1).replace(".0", "");
}

/** Half-hour slots as "weekday:index" keys. Blocks are stored on a 30-minute grid. */
export function toSlots(blocks: AvailabilityBlock[]): Set<string> {
  const slots = new Set<string>();
  for (const b of blocks) {
    const first = Math.floor(minutes(b.start_time) / 30);
    const last = Math.ceil(endMinutes(b.end_time) / 30);
    for (let i = first; i < last; i += 1) slots.add(`${b.weekday}:${i}`);
  }
  return slots;
}

export function fromSlots(slots: Set<string>): AvailabilityBlock[] {
  const blocks: AvailabilityBlock[] = [];
  for (let day = 0; day < 7; day += 1) {
    let start: number | null = null;
    for (let i = 0; i <= SLOTS_PER_DAY; i += 1) {
      const on = i < SLOTS_PER_DAY && slots.has(`${day}:${i}`);
      if (on && start === null) start = i;
      if (!on && start !== null) {
        blocks.push({ weekday: day, start_time: clock(start * 30), end_time: clock(i * 30) });
        start = null;
      }
    }
  }
  return blocks;
}

/** Join overlapping or touching blocks. Returns the blocks and how many were absorbed. */
export function mergeBlocks(blocks: AvailabilityBlock[]): {
  blocks: AvailabilityBlock[];
  merged: number;
} {
  const merged = fromSlots(toSlots(blocks));
  return { blocks: merged, merged: Math.max(0, blocks.length - merged.length) };
}

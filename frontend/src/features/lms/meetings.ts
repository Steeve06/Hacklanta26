import type { components } from "@/api/schema";

export type Meeting = components["schemas"]["Meeting"];

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function clock(t: string): string {
  const [h = 0, m = 0] = t.split(":").map(Number);
  const suffix = h < 12 ? "AM" : "PM";
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${suffix}`;
}

/** "Mon, Wed 10:00 AM–11:15 AM · Hartley Hall 120", one line per distinct time and room. */
export function meetingLines(meetings: Meeting[]): string[] {
  const groups = new Map<string, { days: number[]; text: string }>();
  for (const m of meetings) {
    const key = `${m.start_time}|${m.end_time}|${m.location}`;
    const time = `${clock(m.start_time)}–${clock(m.end_time)}`;
    const text = m.location ? `${time} · ${m.location}` : time;
    const group = groups.get(key) ?? { days: [], text };
    group.days.push(m.weekday);
    groups.set(key, group);
  }
  return [...groups.values()].map((g) => `${g.days.map((d) => DAYS[d]).join(", ")} ${g.text}`);
}

/** Class times are in the campus zone; say so when the student is somewhere else. */
export function campusNote(meetings: Meeting[], studentZone: string): string | null {
  const zone = meetings[0]?.timezone;
  if (!zone || zone === studentZone) return null;
  const name = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "short" })
    .formatToParts(new Date())
    .find((p) => p.type === "timeZoneName")?.value;
  return `Campus time (${name ?? zone})`;
}

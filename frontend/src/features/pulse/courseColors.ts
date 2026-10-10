import type { Schedule } from "./api";

export function courseLookup(schedule: Pick<Schedule, "courses">) {
  const map = new Map(schedule.courses.map((c) => [c.id, c]));
  return (id: number) => map.get(id) ?? { id, code: "Course", title: "", color: "#6b7280" };
}

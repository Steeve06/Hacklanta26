import { formatShortDay } from "@/lib/time";
import type { Deck } from "./api";

/** Format a plain `YYYY-MM-DD` day without shifting it through the viewer's timezone. */
export function formatDeckDay(day: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(undefined, { ...options, timeZone: "UTC" }).format(
    new Date(`${day}T12:00:00Z`),
  );
}

/** One line on what a deck is about, e.g. "Prep for Quiz 2: Hashing (CS 201), due Thu, Oct 15". */
export function focusLine(focus: Deck["focus"], timeZone: string): string {
  if (focus.kind === "upcoming" && focus.assessment_title) {
    const due = focus.due_at ? `, due ${formatShortDay(focus.due_at, timeZone)}` : "";
    return `Prep for ${focus.assessment_title} (${focus.course_code})${due}`;
  }
  if (focus.kind === "review") return "Nothing due this week: a review mix from your courses";
  return "General study cards until your courses have chapters to review";
}

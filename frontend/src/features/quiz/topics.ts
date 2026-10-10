import type { DeckCard } from "./api";

export const TOPIC_LABELS: Record<DeckCard["topic"], string> = {
  study_skills: "Study skills",
  memory: "Memory",
  focus: "Focus",
  wellbeing: "Well-being",
  money: "Money",
  digital: "Digital life",
  science: "Science",
  world: "World",
};

/** Format a plain `YYYY-MM-DD` day without shifting it through the viewer's timezone. */
export function formatDeckDay(day: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(undefined, { ...options, timeZone: "UTC" }).format(
    new Date(`${day}T12:00:00Z`),
  );
}

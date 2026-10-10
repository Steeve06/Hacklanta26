import { Link } from "react-router-dom";
import { EmptyState, QueryView, Skeleton } from "@/components/ui";
import { cx } from "@/lib/cx";
import { formatTime, keyLabel, localDateKey, useTimezone } from "@/lib/time";
import { useNow } from "@/lib/useNow";
import { useCourseCalendar, type ChapterRelease, type CourseCalendar, type Deadline } from "./api";
import { courseLookup } from "./courseColors";

const TYPE_LABEL: Record<string, string> = {
  homework: "Homework",
  quiz: "Quiz",
  discussion: "Discussion",
};
const DONE = new Set(["submitted", "graded"]);

type ClassTime = CourseCalendar["classes"][number];

type Entry =
  | { kind: "class"; at: string; meeting: ClassTime }
  | { kind: "due"; at: string; deadline: Deadline }
  | { kind: "chapter"; at: string; chapter: ChapterRelease };

function entriesByDay(data: CourseCalendar, tz: string): Map<string, Entry[]> {
  const entries: Entry[] = [
    ...data.classes.map((c): Entry => ({ kind: "class", at: c.start, meeting: c })),
    ...data.deadlines.map((d): Entry => ({ kind: "due", at: d.due_at, deadline: d })),
    ...data.chapters.map((c): Entry => ({ kind: "chapter", at: c.available_from, chapter: c })),
  ].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  const map = new Map<string, Entry[]>();
  for (const e of entries) {
    const key = localDateKey(e.at, tz);
    map.set(key, [...(map.get(key) ?? []), e]);
  }
  return map;
}

/** The course schedule from Learning Hub: class meetings, due dates (with any extension) and
 * chapter releases. It shows what the courses expect, not the study plan. */
export function CourseCalendarView({ monday, days }: { monday: string; days: string[] }) {
  const calendar = useCourseCalendar(monday);
  return (
    <QueryView query={calendar} skeleton={<Skeleton className="h-80 w-full" />}>
      {(data) => <Calendar data={data} days={days} />}
    </QueryView>
  );
}

function Calendar({ data, days }: { data: CourseCalendar; days: string[] }) {
  const tz = useTimezone();
  const now = useNow();
  const today = localDateKey(new Date(now), tz);
  const byDay = entriesByDay(data, tz);
  if (byDay.size === 0)
    return (
      <EmptyState
        title="No due dates or new chapters this week"
        body="Check another week, or open a course for its full syllabus."
      />
    );
  return (
    <div className="grid gap-3 md:grid-cols-7 md:gap-0 md:overflow-hidden md:rounded-lg md:border md:border-line md:bg-surface">
      {days.map((day) => {
        const entries = byDay.get(day) ?? [];
        return (
          <section
            key={day}
            aria-label={keyLabel(day, { weekday: "long", month: "long", day: "numeric" })}
            className={cx(
              "flex flex-col gap-2 md:min-h-64 md:border-l md:border-line md:p-2 md:first:border-l-0",
              entries.length === 0 && "hidden md:flex",
              day === today && "md:bg-pine-soft/40",
            )}
          >
            <h2
              className={cx("text-sm font-bold", day === today ? "text-pine-strong" : "text-ink")}
            >
              <span className="md:hidden">
                {keyLabel(day, { weekday: "long", month: "short", day: "numeric" })}
              </span>
              <span className="hidden md:inline">
                {keyLabel(day, { weekday: "short", day: "numeric" })}
              </span>
              {day === today && <span className="sr-only"> (today)</span>}
            </h2>
            <ul className="flex flex-col gap-2">
              {entries.map((e) => (
                <li key={`${e.kind}-${e.at}-${entryId(e)}`}>
                  {e.kind === "class" ? (
                    <ClassItem meeting={e.meeting} data={data} />
                  ) : e.kind === "due" ? (
                    <DueItem deadline={e.deadline} data={data} now={now} />
                  ) : (
                    <ChapterItem chapter={e.chapter} data={data} />
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function entryId(e: Entry): number {
  if (e.kind === "class") return e.meeting.course;
  return e.kind === "due" ? e.deadline.id : e.chapter.id;
}

function ClassItem({ meeting, data }: { meeting: ClassTime; data: CourseCalendar }) {
  const tz = useTimezone();
  const course = courseLookup(data)(meeting.course);
  return (
    <div
      className="rounded-md px-2 py-1.5 text-sm text-white md:text-xs"
      style={{ backgroundColor: course.color }}
    >
      <span className="block font-bold">
        {course.code} class · {formatTime(meeting.start, tz)}–{formatTime(meeting.end, tz)}
      </span>
      {meeting.location && <span className="block opacity-90">{meeting.location}</span>}
    </div>
  );
}

function DueItem({
  deadline,
  data,
  now,
}: {
  deadline: Deadline;
  data: CourseCalendar;
  now: number;
}) {
  const tz = useTimezone();
  const course = courseLookup(data)(deadline.course);
  const done = DONE.has(deadline.status);
  const past = !done && Date.parse(deadline.due_at) < now;
  const state = done ? "Submitted" : past ? "Past due" : deadline.extended ? "Extended" : null;
  return (
    <Link
      to={`/lms/courses/${deadline.course}/assignments/${deadline.id}`}
      className="block rounded-md border-l-4 bg-surface px-2 py-1.5 text-sm hover:underline md:text-xs"
      style={{
        borderLeftColor: course.color,
        backgroundColor: `color-mix(in srgb, ${course.color} 10%, rgb(var(--surface)))`,
      }}
    >
      <span className="block text-ink-soft">
        {course.code} · {TYPE_LABEL[deadline.type] ?? deadline.type} · due{" "}
        {formatTime(deadline.due_at, tz)}
      </span>
      <span className={cx("block font-bold leading-tight", done && "line-through")}>
        {deadline.title}
      </span>
      {state && (
        <span
          className={cx(
            "mt-0.5 block font-bold",
            past ? "text-berry" : done ? "text-pine-strong" : "text-ink-soft",
          )}
        >
          {state}
        </span>
      )}
    </Link>
  );
}

function ChapterItem({ chapter, data }: { chapter: ChapterRelease; data: CourseCalendar }) {
  const course = courseLookup(data)(chapter.course);
  return (
    <Link
      to={`/lms/courses/${chapter.course}/chapters/${chapter.id}`}
      className="block rounded-md border border-dashed px-2 py-1.5 text-sm hover:underline md:text-xs"
      style={{ borderColor: course.color }}
    >
      <span className="block text-ink-soft">{course.code} · Chapter opens</span>
      <span className="block font-bold leading-tight">
        Ch {chapter.order}: {chapter.title}
      </span>
    </Link>
  );
}

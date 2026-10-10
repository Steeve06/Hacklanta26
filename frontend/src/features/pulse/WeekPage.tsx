import { Link, useSearchParams } from "react-router-dom";
import { Button, EmptyState, QueryView, Skeleton } from "@/components/ui";
import { cx } from "@/lib/cx";
import {
  addDays,
  formatTime,
  keyLabel,
  localDateKey,
  localMinutes,
  mondayOf,
  useTimezone,
} from "@/lib/time";
import { useNow } from "@/lib/useNow";
import { useSchedule, type Schedule, type Session } from "./api";
import { CourseCalendarView } from "./CourseCalendar";
import { courseLookup } from "./courseColors";
import { SessionItem } from "./SessionItem";
import { sessionLink } from "./sessionLink";

const HOUR_PX = 56;

const hourLabel = (h: number) => `${h % 12 || 12} ${h < 12 ? "am" : "pm"}`;

export function WeekPage() {
  const tz = useTimezone();
  const now = useNow();
  const [params, setParams] = useSearchParams();
  const thisMonday = mondayOf(localDateKey(new Date(now), tz));
  const monday = mondayOf(params.get("from") ?? thisMonday);
  const calendar = params.get("calendar") === "course" ? "course" : "plan";
  const days = Array.from({ length: 7 }, (_, i) => addDays(monday, i));
  const go = (key: string, to: "plan" | "course" = calendar) => {
    const next: Record<string, string> = {};
    if (key !== thisMonday) next.from = key;
    if (to === "course") next.calendar = "course";
    setParams(next);
  };

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Week</h1>
          <p className="text-ink-soft">
            {keyLabel(monday, { month: "long", day: "numeric" })} –{" "}
            {keyLabel(addDays(monday, 6), { month: "long", day: "numeric" })}
          </p>
        </div>
        <nav aria-label="Change week" className="flex gap-1">
          <Button variant="secondary" size="sm" onClick={() => go(addDays(monday, -7))}>
            Previous week
          </Button>
          {monday !== thisMonday && (
            <Button variant="ghost" size="sm" onClick={() => go(thisMonday)}>
              This week
            </Button>
          )}
          <Button variant="secondary" size="sm" onClick={() => go(addDays(monday, 7))}>
            Next week
          </Button>
        </nav>
      </header>
      <div role="tablist" aria-label="Calendar" className="flex gap-1 border-b border-line">
        {CALENDARS.map((c) => (
          <button
            key={c.id}
            type="button"
            role="tab"
            id={`tab-${c.id}`}
            aria-selected={calendar === c.id}
            aria-controls={`panel-${c.id}`}
            onClick={() => go(monday, c.id)}
            className={cx(
              "-mb-px min-h-11 border-b-2 px-3 font-bold",
              calendar === c.id
                ? "border-pine text-pine-strong"
                : "border-transparent text-ink-soft hover:text-ink",
            )}
          >
            {c.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${calendar}`} aria-labelledby={`tab-${calendar}`}>
        {calendar === "plan" ? (
          <StudyPlan monday={monday} days={days} today={localDateKey(new Date(now), tz)} />
        ) : (
          <>
            <p className="mb-3 text-sm text-ink-soft">
              Due dates and new chapters from your courses. Your study sessions are under Study
              plan.
            </p>
            <CourseCalendarView monday={monday} days={days} />
          </>
        )}
      </div>
    </div>
  );
}

const CALENDARS = [
  { id: "plan", label: "Study plan" },
  { id: "course", label: "Course calendar" },
] as const;

function StudyPlan({ monday, days, today }: { monday: string; days: string[]; today: string }) {
  const schedule = useSchedule("week", monday);
  return (
    <QueryView query={schedule} skeleton={<Skeleton className="h-[32rem] w-full" />}>
      {(data) => (
        <>
          <div className="hidden md:block">
            <WeekGrid data={data} days={days} today={today} />
          </div>
          <div className="md:hidden">
            <WeekList data={data} days={days} />
          </div>
        </>
      )}
    </QueryView>
  );
}

function bucket<T>(items: T[], key: (item: T) => string): Map<string, T[]> {
  const map = new Map<string, T[]>();
  for (const item of items) map.set(key(item), [...(map.get(key(item)) ?? []), item]);
  return map;
}

function WeekGrid({ data, days, today }: { data: Schedule; days: string[]; today: string }) {
  const tz = useTimezone();
  const course = courseLookup(data);
  const sessions = data.sessions.filter((s) => s.status !== "rescheduled");
  const byDay = bucket(sessions, (s) => localDateKey(s.start, tz));
  const starts = sessions.map((s) => localMinutes(s.start, tz));
  const ends = sessions.map((s) => localMinutes(s.start, tz) + s.minutes);
  const first = Math.min(8 * 60, ...starts);
  const last = Math.max(21 * 60, ...ends);
  const startHour = Math.floor(first / 60);
  const endHour = Math.ceil(last / 60);
  const hours = Array.from({ length: endHour - startHour }, (_, i) => startHour + i);

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <div className="grid grid-cols-[3.5rem_repeat(7,minmax(0,1fr))] border-b border-line">
        <div />
        {days.map((day) => (
          <div
            key={day}
            className={cx("border-l border-line px-2 py-2", day === today && "bg-pine-soft")}
          >
            <p className={cx("text-sm font-bold", day === today ? "text-pine-strong" : "text-ink")}>
              {keyLabel(day, { weekday: "short", day: "numeric" })}
              {day === today && <span className="sr-only"> (today)</span>}
            </p>
          </div>
        ))}
      </div>
      <div
        className="relative grid grid-cols-[3.5rem_repeat(7,minmax(0,1fr))]"
        style={{ height: hours.length * HOUR_PX }}
      >
        <div className="relative">
          {hours.map((h, i) => (
            <span
              key={h}
              className="absolute right-2 -translate-y-1/2 text-xs text-ink-soft"
              style={{ top: i * HOUR_PX }}
            >
              {i === 0 ? "" : hourLabel(h)}
            </span>
          ))}
        </div>
        {days.map((day) => (
          <div
            key={day}
            className={cx("relative border-l border-line", day === today && "bg-pine-soft/40")}
          >
            {hours.map((h, i) => (
              <div
                key={h}
                aria-hidden="true"
                className="absolute inset-x-0 border-t border-line/60"
                style={{ top: i * HOUR_PX }}
              />
            ))}
            {(byDay.get(day) ?? []).map((s) => (
              <GridSession
                key={s.id}
                session={s}
                color={course(s.course).color}
                top={((localMinutes(s.start, tz) - startHour * 60) / 60) * HOUR_PX}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function GridSession({ session, color, top }: { session: Session; color: string; top: number }) {
  const tz = useTimezone();
  const height = Math.max(22, (session.minutes / 60) * HOUR_PX - 2);
  return (
    <Link
      to={sessionLink(session, session.course)}
      className={cx(
        "absolute inset-x-1 overflow-hidden rounded-sm border-l-4 bg-surface px-1.5 py-0.5 text-xs shadow-sm hover:z-10 hover:shadow-md",
        session.status !== "planned" && "opacity-60",
      )}
      style={{
        top,
        height,
        borderLeftColor: color,
        backgroundColor: `color-mix(in srgb, ${color} 12%, rgb(var(--surface)))`,
      }}
      title={`${formatTime(session.start, tz)}–${formatTime(session.end, tz)} ${session.task_title}`}
    >
      <span className="block font-bold leading-tight">
        {session.task_title.replace(
          / · .*?(Read |Draft |Finish and submit |Review and take )/,
          " · ",
        )}
      </span>
      {height > 34 && (
        <span className="block truncate text-ink-soft">
          {formatTime(session.start, tz)} · {session.minutes}m
        </span>
      )}
    </Link>
  );
}

function WeekList({ data, days }: { data: Schedule; days: string[] }) {
  const tz = useTimezone();
  const course = courseLookup(data);
  const sessions = data.sessions.filter((s) => s.status !== "rescheduled");
  if (sessions.length === 0) {
    return (
      <EmptyState
        title="Nothing planned this week"
        body="Check another week or adjust your availability in Settings."
      />
    );
  }
  return (
    <div className="flex flex-col gap-5">
      {days.map((day) => {
        const daySessions = sessions.filter((s) => localDateKey(s.start, tz) === day);
        if (daySessions.length === 0) return null;
        return (
          <section
            key={day}
            aria-label={keyLabel(day, { weekday: "long", month: "long", day: "numeric" })}
            className="flex flex-col gap-2"
          >
            <h2 className="font-bold">
              {keyLabel(day, { weekday: "long", month: "short", day: "numeric" })}
            </h2>
            {daySessions.map((s) => (
              <SessionItem key={s.id} session={s} color={course(s.course).color} />
            ))}
          </section>
        );
      })}
    </div>
  );
}

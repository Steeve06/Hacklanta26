import { Link } from "react-router-dom";
import { QueryView, Skeleton } from "@/components/ui";
import { cx } from "@/lib/cx";
import { addDays, keyLabel, localDateKey, mondayOf, useTimezone } from "@/lib/time";
import { useNow } from "@/lib/useNow";
import { useSchedule, type Schedule } from "./api";
import { OverloadPanel } from "./OverloadPanel";
import { percent } from "@/lib/percent";

export function OverallPage() {
  const schedule = useSchedule("overall");
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Term overview</h1>
        <p className="text-ink-soft">
          The whole term by course: planned study per week and every due date.
        </p>
      </header>
      <QueryView query={schedule} skeleton={<Skeleton className="h-80 w-full" />}>
        {(data) => (
          <>
            {data.overload_report && <OverloadPanel report={data.overload_report} />}
            <Timeline data={data} />
            <Legend />
          </>
        )}
      </QueryView>
    </div>
  );
}

function Timeline({ data }: { data: Schedule }) {
  const tz = useTimezone();
  const now = useNow();
  if (!data.term_start || !data.term_end) return null;
  const firstMonday = mondayOf(data.term_start);
  const weeks: string[] = [];
  for (let w = firstMonday; w <= data.term_end; w = addDays(w, 7)) weeks.push(w);
  const thisWeek = mondayOf(localDateKey(new Date(now), tz));
  const minutes = (courseId: number, week: string, done: boolean) =>
    data.sessions
      .filter((s) => s.course === courseId && mondayOf(localDateKey(s.start, tz)) === week)
      .filter((s) =>
        done ? s.status === "done" || s.status === "partial" : s.status === "planned",
      )
      .reduce((sum, s) => sum + (done ? s.completed_minutes : s.minutes), 0);
  const peak = Math.max(
    60,
    ...data.courses.flatMap((c) =>
      weeks.map((w) => minutes(c.id, w, false) + minutes(c.id, w, true)),
    ),
  );

  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full min-w-[46rem] border-collapse text-sm">
        <caption className="sr-only">Study minutes and due dates per course and week</caption>
        <thead>
          <tr>
            <th scope="col" className="w-28 px-3 py-2 text-left font-bold">
              Course
            </th>
            {weeks.map((w, i) => (
              <th
                key={w}
                scope="col"
                className={cx(
                  "px-1 py-2 text-center text-xs font-bold",
                  w === thisWeek ? "text-pine-strong" : "text-ink-soft",
                )}
              >
                <span className="block">W{i + 1}</span>
                <span className="block font-normal">
                  {keyLabel(w, { month: "numeric", day: "numeric" })}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.courses.map((course) => (
            <tr key={course.id} className="border-t border-line">
              <th scope="row" className="px-3 py-3 text-left">
                <span className="flex items-center gap-2 font-bold">
                  <span
                    aria-hidden="true"
                    className="h-3 w-3 rounded-full"
                    style={{ background: course.color }}
                  />
                  {course.code}
                </span>
              </th>
              {weeks.map((w) => {
                const planned = minutes(course.id, w, false);
                const done = minutes(course.id, w, true);
                const due = data.deadlines.filter(
                  (d) => d.course === course.id && mondayOf(localDateKey(d.due_at, tz)) === w,
                );
                return (
                  <td
                    key={w}
                    className={cx(
                      "h-24 px-0.5 pb-1 align-bottom",
                      w === thisWeek && "bg-pine-soft/50",
                    )}
                  >
                    <div className="flex h-full flex-col justify-end gap-0.5">
                      <div className="flex flex-wrap justify-center gap-0.5">
                        {due.map((d) => (
                          <Link
                            key={d.id}
                            to={`/lms/courses/${d.course}/assignments/${d.id}`}
                            title={`${d.title} (${percent(d.weight_pct)})`}
                            aria-label={`Due: ${d.title}`}
                            className={cx(
                              "block h-3 w-3 rotate-45 border-2",
                              d.status === "missed"
                                ? "border-berry bg-berry"
                                : ["submitted", "late", "graded", "excused"].includes(d.status)
                                  ? "border-ink-faint bg-ink-faint"
                                  : "bg-surface",
                            )}
                            style={
                              ["missed", "submitted", "late", "graded", "excused"].includes(
                                d.status,
                              )
                                ? undefined
                                : { borderColor: course.color }
                            }
                          />
                        ))}
                      </div>
                      <div
                        className="mx-auto w-4/5 rounded-t-sm"
                        style={{
                          height: `${(done / peak) * 52}px`,
                          background: "rgb(var(--ink-faint))",
                        }}
                        title={`${done} min done`}
                      />
                      <div
                        className="mx-auto w-4/5 rounded-t-sm"
                        style={{ height: `${(planned / peak) * 52}px`, background: course.color }}
                        title={`${planned} min planned`}
                      />
                      <span className="sr-only">
                        {planned} minutes planned, {done} done, {due.length} due
                      </span>
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Legend() {
  return (
    <ul className="flex flex-wrap gap-4 text-sm text-ink-soft" aria-label="Legend">
      <li className="flex items-center gap-2">
        <span aria-hidden="true" className="h-3 w-4 rounded-sm bg-pine" /> Planned study
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden="true" className="h-3 w-4 rounded-sm bg-ink-faint" /> Already studied
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden="true" className="h-3 w-3 rotate-45 border-2 border-ink" /> Due date
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden="true" className="h-3 w-3 rotate-45 border-2 border-berry bg-berry" />{" "}
        Missed
      </li>
    </ul>
  );
}

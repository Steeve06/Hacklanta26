import { useState } from "react";
import { Link } from "react-router-dom";
import { ChipGroup, EmptyState, QueryView, Skeleton } from "@/components/ui";
import { DueTime } from "@/components/Time";
import { useMe } from "@/features/auth/hooks";
import { useAssessments, type Assessment } from "./api";
import { typeLabels } from "./labels";
import { StatusPill } from "./StatusPill";
import { useNumericParam } from "./useIds";
import { percent } from "@/lib/percent";

type TypeFilter = "all" | "homework" | "discussion" | "quiz";
type StatusFilter = "all" | "todo" | "done" | "missed";

const done = new Set(["submitted", "late", "graded", "excused"]);

function matchesStatus(a: Assessment, filter: StatusFilter): boolean {
  if (filter === "all") return true;
  if (filter === "done") return done.has(a.status ?? "");
  if (filter === "missed") return a.status === "missed";
  return !done.has(a.status ?? "") && a.status !== "missed";
}

export function AssignmentsTab() {
  const courseId = useNumericParam("courseId");
  const assessments = useAssessments(courseId);
  const me = useMe();
  const isStudent = me.data?.role === "student";
  const [type, setType] = useState<TypeFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("all");

  return (
    <section aria-labelledby="assignments-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="assignments-heading" className="text-lg font-bold">
          Assignments
        </h2>
        {!isStudent && (
          <Link
            to={`/lms/courses/${courseId}/assignments/new`}
            className="inline-flex min-h-11 items-center rounded-md bg-pine px-4 font-bold text-on-pine"
          >
            New assignment
          </Link>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <ChipGroup<TypeFilter>
          label="Filter by type"
          value={type}
          onChange={setType}
          options={[
            { value: "all", label: "All types" },
            { value: "homework", label: "Homework" },
            { value: "discussion", label: "Discussions" },
            { value: "quiz", label: "Quizzes" },
          ]}
        />
        {isStudent && (
          <ChipGroup<StatusFilter>
            label="Filter by status"
            value={status}
            onChange={setStatus}
            options={[
              { value: "all", label: "Any status" },
              { value: "todo", label: "To do" },
              { value: "done", label: "Done" },
              { value: "missed", label: "Missed" },
            ]}
          />
        )}
      </div>
      <QueryView
        query={assessments}
        isEmpty={(d) => d.length === 0}
        empty={{
          title: "No assignments yet",
          body: "The instructor hasn't posted any assignments for this course.",
        }}
        skeleton={
          <div className="flex flex-col gap-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        }
      >
        {(data) => {
          const visible = data.filter(
            (a) => (type === "all" || a.type === type) && matchesStatus(a, status),
          );
          if (visible.length === 0)
            return (
              <EmptyState
                title="Nothing matches these filters"
                body="Try another type or status."
              />
            );
          return (
            <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
              {visible.map((a) => (
                <li key={a.id}>
                  <Link
                    to={`/lms/courses/${courseId}/assignments/${a.id}`}
                    className="flex min-h-16 flex-col gap-1 px-4 py-3 hover:bg-sunken sm:flex-row sm:items-center sm:gap-4"
                  >
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="text-xs font-bold text-ink-soft">
                        {typeLabels[a.type]} · {percent(a.weight_pct)} of grade
                        {!a.published && " · Hidden from students"}
                      </span>
                      <span className="font-bold">{a.title}</span>
                    </span>
                    <span className="flex items-center gap-3 text-sm text-ink-soft">
                      <DueTime iso={a.effective_due_at} />
                      {a.extended && <span className="font-bold text-pine-strong">Extended</span>}
                      <StatusPill status={a.status} overdue={a.overdue} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          );
        }}
      </QueryView>
    </section>
  );
}

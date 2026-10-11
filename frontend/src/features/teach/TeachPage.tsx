import { Link, Navigate } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { DueTime } from "@/components/Time";
import { QueryView, Skeleton } from "@/components/ui";
import { useMe } from "@/features/auth/hooks";
import { homeFor } from "@/features/auth/redirects";
import { typeLabels } from "@/features/lms/labels";
import { meetingLines } from "@/features/lms/meetings";
import { cx } from "@/lib/cx";
import { useTeachingOverview, type TeachingCourse } from "./api";

export function TeachPage() {
  const me = useMe();
  const overview = useTeachingOverview();
  if (me.data?.role === "student") return <Navigate to={homeFor(me.data)} replace />;
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">
          {me.data ? `Welcome, ${me.data.first_name}` : "Your teaching"}
        </h1>
        <p className="text-ink-soft">
          Your courses are set up. Add chapters, assignments, discussions and quizzes, and your
          students see them right away.
        </p>
      </header>
      <QueryView
        query={overview}
        isEmpty={(data) => data.length === 0}
        empty={{
          title: "No course is linked to your account",
          body: "Ask your department to register your course with the email you signed up with.",
        }}
        skeleton={<Skeleton className="h-72 w-full" />}
      >
        {(data) => (
          <ul className="flex flex-col gap-6">
            {data.map((course) => (
              <li key={course.id}>
                <CoursePanel course={course} />
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </div>
  );
}

const actions = [
  { key: "chapter", label: "Add a chapter", path: "chapters/new" },
  { key: "homework", label: "Add an assignment", path: "assignments/new?type=homework" },
  { key: "discussion", label: "Start a discussion", path: "assignments/new?type=discussion" },
  { key: "quiz", label: "Create a quiz", path: "assignments/new?type=quiz" },
] as const;

function CoursePanel({ course }: { course: TeachingCourse }) {
  const base = `/lms/courses/${course.id}`;
  const steps = [
    {
      done: course.chapters > 0,
      label: "Add your first chapter",
      hint: "Students read it in Courses, and it feeds their daily study cards.",
    },
    {
      done: course.homework > 0,
      label: "Post an assignment",
      hint: "It lands in every student's plan with study sessions before the due date.",
    },
    {
      done: course.discussions > 0,
      label: "Start a discussion",
      hint: "Students post and reply to each other.",
    },
    {
      done: course.quizzes > 0,
      label: "Create a quiz",
      hint: "Timed, auto-graded, multiple choice or true/false.",
    },
  ];
  const started = steps.some((s) => s.done);
  const stats = [
    { label: "Students", value: course.students, to: undefined },
    { label: "Chapters", value: course.chapters, to: base },
    { label: "Assignments", value: course.homework, to: `${base}/assignments` },
    { label: "Discussions", value: course.discussions, to: `${base}/assignments` },
    { label: "Quizzes", value: course.quizzes, to: `${base}/assignments` },
    { label: "To grade", value: course.to_grade, to: `${base}/assignments` },
  ];
  return (
    <section
      aria-labelledby={`course-${course.id}`}
      className="flex flex-col gap-5 rounded-lg border border-line bg-surface p-4 md:p-5"
      style={{ borderTop: `6px solid ${course.color}` }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-ink-soft">
            {course.code} · {course.term}
          </p>
          <h2 id={`course-${course.id}`} className="text-xl font-bold">
            {course.title}
          </h2>
          {meetingLines(course.meetings).map((line) => (
            <p key={line} className="text-sm">
              {line}
            </p>
          ))}
        </div>
        <Link
          to={base}
          className="inline-flex min-h-11 items-center gap-1 rounded-md border border-line px-4 font-bold hover:bg-sunken"
        >
          Open course <Icon name="chevron" className="h-4 w-4" />
        </Link>
      </div>

      <dl className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {stats.map((s) => {
          const body = (
            <>
              <dt className="text-xs font-bold text-ink-soft">{s.label}</dt>
              <dd className="font-display text-2xl font-bold">{s.value}</dd>
            </>
          );
          return (
            <div
              key={s.label}
              className={cx(
                "rounded-md bg-sunken p-3",
                s.label === "To grade" && s.value > 0 && "bg-berry-soft",
              )}
            >
              {s.to ? (
                <Link to={s.to} className="block hover:underline">
                  {body}
                </Link>
              ) : (
                body
              )}
            </div>
          );
        })}
      </dl>

      <div className="flex flex-col gap-2">
        <h3 className="font-bold">Add to your course</h3>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {actions.map((a) => (
            <Link
              key={a.key}
              to={`${base}/${a.path}`}
              className="flex min-h-11 items-center justify-center rounded-md bg-pine px-4 text-center font-bold text-on-pine hover:bg-pine-strong"
            >
              {a.label}
            </Link>
          ))}
        </div>
        <Link to={`${base}/syllabus`} className="self-start text-sm font-bold text-pine underline">
          Edit syllabus and grading
        </Link>
      </div>

      {!steps.every((s) => s.done) && (
        <div className="flex flex-col gap-2">
          <h3 className="font-bold">{started ? "Keep going" : "Get your course ready"}</h3>
          <ol className="flex flex-col gap-2">
            {steps.map((s, i) => (
              <li key={s.label} className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className={cx(
                    "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 text-sm font-bold",
                    s.done ? "border-pine bg-pine text-on-pine" : "border-line text-ink-soft",
                  )}
                >
                  {s.done ? <Icon name="check" className="h-3.5 w-3.5" /> : i + 1}
                </span>
                <span>
                  <span className={cx("font-bold", s.done && "line-through opacity-70")}>
                    {s.label}
                  </span>
                  <span className="sr-only">{s.done ? " (done)" : ""}</span>
                  <span className="block text-sm text-ink-soft">{s.hint}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <p className="text-sm">
        {course.next_due ? (
          <>
            <span className="font-bold">Next due:</span> {typeLabels[course.next_due.type]}{" "}
            {course.next_due.title} · <DueTime iso={course.next_due.due_at} />
          </>
        ) : (
          <span className="text-ink-soft">Nothing due yet.</span>
        )}
        {course.hidden > 0 && (
          <span className="text-ink-soft"> · {course.hidden} hidden from students</span>
        )}
      </p>
    </section>
  );
}

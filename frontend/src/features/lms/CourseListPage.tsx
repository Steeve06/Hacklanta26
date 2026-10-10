import { Link } from "react-router-dom";
import { ProgressBar, QueryView, Skeleton } from "@/components/ui";
import { DueTime } from "@/components/Time";
import { useMe } from "@/features/auth/hooks";
import { CourseMoodBadge } from "@/features/pulse/CourseMoodBadge";
import { useCourses, type Course } from "./api";
import { typeLabels } from "./labels";

export function CourseListPage() {
  const courses = useCourses();
  const me = useMe();
  const isStudent = me.data?.role === "student";
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Courses</h1>
        <p className="text-ink-soft">
          {isStudent ? "Everything you're enrolled in this term." : "Courses you teach this term."}
        </p>
      </header>
      <QueryView
        query={courses}
        isEmpty={(data) => data.length === 0}
        empty={{
          title: "No courses yet",
          body: "When you're enrolled in a course it shows up here.",
        }}
        skeleton={<CourseListSkeleton />}
      >
        {(data) => (
          <ul className="grid gap-4 md:grid-cols-2">
            {data.map((course) => (
              <li key={course.id}>
                <CourseRow course={course} showMood={isStudent} />
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </div>
  );
}

function CourseRow({ course, showMood }: { course: Course; showMood: boolean }) {
  const pct = course.chapters_total ? (course.chapters_completed / course.chapters_total) * 100 : 0;
  return (
    <Link
      to={`/lms/courses/${course.id}`}
      className="group flex h-full flex-col gap-3 rounded-lg border border-line bg-surface p-4 transition-colors hover:border-ink-faint"
      style={{ borderLeft: `6px solid ${course.color}` }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-ink-soft">{course.code}</p>
          <h2 className="text-lg font-bold group-hover:underline">{course.title}</h2>
          <p className="text-sm text-ink-soft">{course.instructor_name}</p>
        </div>
        {showMood && <CourseMoodBadge courseId={course.id} />}
      </div>
      <div className="mt-auto flex flex-col gap-2">
        <p className="text-sm">
          {course.next_due ? (
            <>
              <span className="font-bold">{typeLabels[course.next_due.type]}:</span>{" "}
              {course.next_due.title} · <DueTime iso={course.next_due.due_at} />
            </>
          ) : (
            <span className="text-ink-soft">Nothing due soon</span>
          )}
        </p>
        <ProgressBar
          value={pct}
          label={`${course.chapters_completed} of ${course.chapters_total} chapters completed`}
        />
        <p className="text-xs text-ink-soft">
          {course.chapters_completed} of {course.chapters_total} chapters completed
        </p>
      </div>
    </Link>
  );
}

function CourseListSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="mt-4 h-2 w-full" />
        </div>
      ))}
    </div>
  );
}

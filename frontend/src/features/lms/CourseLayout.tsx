import { Outlet } from "react-router-dom";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { ErrorState, RouteTabs, Skeleton } from "@/components/ui";
import { errorMessage } from "@/api/client";
import { useCourse } from "./api";
import { useNumericParam } from "./useIds";

export function CourseLayout() {
  const courseId = useNumericParam("courseId");
  const course = useCourse(courseId);
  const base = `/lms/courses/${courseId}`;
  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs
        items={[{ label: "Courses", to: "/lms" }, { label: course.data?.code ?? "Course" }]}
      />
      <header className="flex flex-col gap-1">
        {course.isPending ? (
          <>
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-8 w-64" />
          </>
        ) : course.isError ? (
          <ErrorState message={errorMessage(course.error)} onRetry={() => void course.refetch()} />
        ) : (
          <>
            <p className="font-bold text-ink-soft">
              <span
                aria-hidden="true"
                className="mr-2 inline-block h-3 w-3 rounded-full align-middle"
                style={{ background: course.data.color }}
              />
              {course.data.code}
            </p>
            <h1 className="text-2xl font-bold">{course.data.title}</h1>
          </>
        )}
      </header>
      <RouteTabs
        label="Course sections"
        tabs={[
          { to: base, label: "Content", end: true },
          { to: `${base}/assignments`, label: "Assignments" },
          { to: `${base}/syllabus`, label: "Syllabus" },
        ]}
      />
      <Outlet />
    </div>
  );
}

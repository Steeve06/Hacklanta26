import { QueryView, Skeleton } from "@/components/ui";
import { useCourses } from "@/features/lms/api";
import type { StepProps } from "../stepTypes";
import { StepFooter } from "../StepFooter";

export function CoursesStep({ saving, submit, error }: StepProps) {
  const courses = useCourses();
  const count = courses.data?.length ?? 0;
  return (
    <section aria-label="Your courses" className="flex flex-col gap-4">
      <p className="text-ink-soft">
        Your plan covers every chapter, assignment, discussion and quiz in these courses.
      </p>
      <QueryView
        query={courses}
        skeleton={<Skeleton className="h-36 w-full" />}
        isEmpty={(d) => d.length === 0}
        empty={{
          title: "You aren't enrolled in any courses",
          body: "Ask your instructor to add you, then come back. Your answers so far are saved.",
        }}
      >
        {(data) => (
          <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
            {data.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3">
                <span
                  aria-hidden="true"
                  className="h-3 w-3 rounded-full"
                  style={{ background: c.color }}
                />
                <span className="font-bold">{c.code}</span>
                <span>{c.title}</span>
                <span className="ml-auto text-sm text-ink-soft">{c.instructor_name}</span>
              </li>
            ))}
          </ul>
        )}
      </QueryView>
      <StepFooter
        onNext={() => submit({})}
        nextLabel="These are right"
        nextDisabled={count === 0}
        hint={
          courses.isSuccess && count === 0 ? "You need at least one course to continue." : undefined
        }
        saving={saving}
        error={error}
      />
    </section>
  );
}

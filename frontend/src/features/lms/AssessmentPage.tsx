import DOMPurify from "dompurify";
import { Link } from "react-router-dom";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { QueryView, Skeleton, SkeletonLines } from "@/components/ui";
import { ExactTime } from "@/components/Time";
import { useMe } from "@/features/auth/hooks";
import { relativeDue } from "@/lib/time";
import { useAssessment, useCourse, type AssessmentDetail } from "./api";
import { DiscussionPanel } from "./DiscussionPanel";
import { HomeworkPanel } from "./HomeworkPanel";
import { InstructorPanel } from "./InstructorPanel";
import { QuizPanel } from "./QuizPanel";
import { typeLabels } from "./labels";
import { StatusPill } from "./StatusPill";
import { useNumericParam } from "./useIds";
import { percent } from "@/lib/percent";

export function AssessmentPage() {
  const courseId = useNumericParam("courseId");
  const assessmentId = useNumericParam("assessmentId");
  const course = useCourse(courseId);
  const assessment = useAssessment(assessmentId);
  const me = useMe();
  const isStudent = me.data?.role === "student";

  return (
    <article className="flex flex-col gap-4">
      <Breadcrumbs
        items={[
          { label: "Courses", to: "/lms" },
          { label: course.data?.code ?? "Course", to: `/lms/courses/${courseId}` },
          { label: "Assignments", to: `/lms/courses/${courseId}/assignments` },
          { label: assessment.data?.title ?? "Assignment" },
        ]}
      />
      <QueryView
        query={assessment}
        skeleton={
          <div className="flex flex-col gap-4">
            <Skeleton className="h-9 w-2/3" />
            <Skeleton className="h-16 w-full" />
            <SkeletonLines lines={5} />
          </div>
        }
      >
        {(data) => (
          <>
            <Header assessment={data} isStudent={isStudent} courseId={courseId} />
            <section aria-labelledby="instructions" className="max-w-prose">
              <h2 id="instructions" className="sr-only">
                Instructions
              </h2>
              <div
                className="prose-chapter"
                dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(data.instructions_html) }}
              />
            </section>
            {isStudent && data.type === "homework" && <HomeworkPanel assessment={data} />}
            {data.type === "discussion" && (
              <DiscussionPanel assessment={data} canPost={isStudent} />
            )}
            {isStudent && data.type === "quiz" && <QuizPanel assessment={data} />}
            {!isStudent && <InstructorPanel assessment={data} />}
          </>
        )}
      </QueryView>
    </article>
  );
}

function Header({
  assessment,
  isStudent,
  courseId,
}: {
  assessment: AssessmentDetail;
  isStudent: boolean;
  courseId: number;
}) {
  return (
    <header className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-bold text-ink-soft">
          {assessment.course_code} · {typeLabels[assessment.type]}
        </span>
        {isStudent && <StatusPill status={assessment.status} overdue={assessment.overdue} />}
      </div>
      <h1 className="text-2xl font-bold md:text-3xl">{assessment.title}</h1>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:flex sm:flex-wrap">
        <div>
          <dt className="text-ink-soft">Due</dt>
          <dd className="font-bold">
            <ExactTime iso={assessment.effective_due_at} /> (
            {relativeDue(assessment.effective_due_at)})
            {assessment.extended && <span className="ml-1 text-pine-strong">extended for you</span>}
          </dd>
        </div>
        {assessment.effective_cutoff_at && (
          <div>
            <dt className="text-ink-soft">Late cut-off</dt>
            <dd className="font-bold">
              <ExactTime iso={assessment.effective_cutoff_at} />
            </dd>
          </div>
        )}
        <div>
          <dt className="text-ink-soft">Worth</dt>
          <dd className="font-bold">
            {assessment.points} points · {percent(assessment.weight_pct)} of grade
          </dd>
        </div>
      </dl>
      {!isStudent && (
        <Link
          to={`/lms/courses/${courseId}/assignments/${assessment.id}/edit`}
          className="self-start text-sm font-bold text-pine underline"
        >
          Edit assignment
        </Link>
      )}
    </header>
  );
}

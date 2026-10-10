import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { QuestionField } from "@/components/QuestionField";
import { Button, QueryView, Skeleton, toast } from "@/components/ui";
import { formatClock, useCountdown } from "@/lib/useCountdown";
import { useAttempt, useSaveAnswers, useSubmitAttempt, type QuizAttempt } from "./api";
import { useNumericParam } from "./useIds";

export function AttemptPage() {
  const courseId = useNumericParam("courseId");
  const attemptId = useNumericParam("attemptId");
  const attempt = useAttempt(attemptId);
  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs
        items={[
          { label: "Courses", to: "/lms" },
          { label: "Assignments", to: `/lms/courses/${courseId}/assignments` },
          { label: "Quiz attempt" },
        ]}
      />
      <QueryView
        query={attempt}
        skeleton={
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-40 w-full" />
            ))}
          </div>
        }
      >
        {(data) => (
          <AttemptBody attempt={data} courseId={courseId} onExpire={() => void attempt.refetch()} />
        )}
      </QueryView>
    </div>
  );
}

function AttemptBody({
  attempt,
  courseId,
  onExpire,
}: {
  attempt: QuizAttempt;
  courseId: number;
  onExpire: () => void;
}) {
  const [answers, setAnswers] = useState<Record<string, number>>(
    () => attempt.answers as Record<string, number>,
  );
  const save = useSaveAnswers(attempt.id);
  const submit = useSubmitAttempt(attempt.id);
  const remaining = useCountdown(attempt.submitted_at ? null : attempt.deadline_at);
  const expiredRef = useRef(false);
  const done = Boolean(attempt.submitted_at);

  useEffect(() => {
    if (remaining === 0 && !done && !expiredRef.current) {
      expiredRef.current = true;
      onExpire();
    }
  }, [remaining, done, onExpire]);

  function choose(questionId: number, value: number) {
    const next = { ...answers, [String(questionId)]: value };
    setAnswers(next);
    save.mutate({ [String(questionId)]: value });
  }

  const correct = new Map((attempt.results ?? []).map((r) => [r.question, r.correct_index]));
  const answeredCount = Object.keys(answers).length;

  return (
    <div className="flex flex-col gap-4">
      <header className="sticky top-14 z-10 -mx-4 flex flex-wrap items-center justify-between gap-3 border-b border-line bg-paper/95 px-4 py-3 md:top-0 md:mx-0 md:rounded-md md:border">
        <h1 className="text-xl font-bold">Attempt {attempt.attempt_no}</h1>
        {done ? (
          <p className="font-bold" role="status">
            Score: {attempt.score}
            {attempt.auto_submitted && " · submitted automatically when time ran out"}
          </p>
        ) : (
          <p className="font-bold tabular-nums" aria-live="off">
            <span className="sr-only">Time left: </span>
            {remaining !== null ? formatClock(remaining) : "--:--"} left · {answeredCount} of{" "}
            {attempt.questions.length} answered
          </p>
        )}
      </header>
      <ol className="flex flex-col gap-3">
        {attempt.questions.map((q, i) => (
          <li key={q.id}>
            <QuestionField
              index={i}
              prompt={q.prompt}
              options={q.options as string[]}
              value={answers[String(q.id)]}
              onChange={(v) => choose(q.id, v)}
              disabled={done || submit.isPending}
              correctIndex={correct.get(q.id)}
            />
          </li>
        ))}
      </ol>
      {done ? (
        <Link
          to={`/lms/courses/${courseId}/assignments/${attempt.assessment}`}
          className="inline-flex min-h-11 items-center self-start rounded-md bg-pine px-4 font-bold text-on-pine"
        >
          Back to the quiz
        </Link>
      ) : (
        <Button
          className="self-start"
          pending={submit.isPending}
          pendingLabel="Submitting…"
          onClick={() =>
            submit.mutate(answers, { onError: (err) => toast.error(errorMessage(err)) })
          }
        >
          Submit answers
        </Button>
      )}
    </div>
  );
}

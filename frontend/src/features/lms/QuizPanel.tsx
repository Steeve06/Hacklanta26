import { useNavigate } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Button, toast } from "@/components/ui";
import { useNow } from "@/lib/useNow";
import { useStartAttempt, type AssessmentDetail } from "./api";

export function QuizPanel({ assessment }: { assessment: AssessmentDetail }) {
  const start = useStartAttempt();
  const navigate = useNavigate();
  const best = assessment.submissions.find((s) => s.score !== null && s.score !== undefined);
  const remaining = assessment.max_attempts - assessment.attempts_used;
  const now = useNow();
  const closed =
    now > new Date(assessment.effective_cutoff_at ?? assessment.effective_due_at).getTime();
  const notOpen = now < new Date(assessment.open_at).getTime();

  return (
    <section
      aria-labelledby="quiz-heading"
      className="flex max-w-prose flex-col gap-3 border-t border-line pt-4"
    >
      <h2 id="quiz-heading" className="text-lg font-bold">
        Quiz
      </h2>
      <dl className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <dt className="text-ink-soft">Questions</dt>
          <dd className="font-bold">{assessment.questions_count}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Time limit</dt>
          <dd className="font-bold">{assessment.time_limit_minutes} min</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Attempts left</dt>
          <dd className="font-bold">{Math.max(0, remaining)}</dd>
        </div>
      </dl>
      {best && (
        <p className="font-bold">
          Best score: {best.score} / {assessment.points}
        </p>
      )}
      {assessment.status === "excused" ? (
        <p className="text-sm text-ink-soft">You're excused from this quiz.</p>
      ) : notOpen ? (
        <p className="text-sm text-ink-soft">This quiz isn't open yet.</p>
      ) : closed ? (
        <p className="text-sm text-ink-soft">This quiz has closed.</p>
      ) : remaining <= 0 ? (
        <p className="text-sm text-ink-soft">You've used all your attempts.</p>
      ) : (
        <Button
          className="self-start"
          pending={start.isPending}
          pendingLabel="Starting…"
          onClick={() =>
            start.mutate(assessment.id, {
              onSuccess: (attempt) =>
                navigate(`/lms/courses/${assessment.course}/attempts/${attempt.id}`),
              onError: (err) => toast.error(errorMessage(err)),
            })
          }
        >
          {assessment.attempts_used > 0 ? "Start another attempt" : "Start quiz"}
        </Button>
      )}
      <p className="text-xs text-ink-soft">
        The timer starts when you begin and keeps running if you leave the page. Unanswered
        questions count as wrong when time runs out.
      </p>
    </section>
  );
}

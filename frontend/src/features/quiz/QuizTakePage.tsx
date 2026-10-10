import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { Confetti } from "@/components/Confetti";
import { Mascot } from "@/components/mascot/Mascot";
import { QuestionField } from "@/components/QuestionField";
import { Button, QueryView, Skeleton, toast } from "@/components/ui";
import { useNumericParam } from "@/features/lms/useIds";
import { formatExact, useTimezone } from "@/lib/time";
import { useQuiz, useStartQuiz, useSubmitQuiz, type QuizDetail } from "./api";
import { TimeLeft } from "./QuizCards";
import { quizName } from "./quizName";

export function QuizTakePage() {
  const id = useNumericParam("quizId");
  const quiz = useQuiz(id);
  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <Breadcrumbs
        items={[
          { label: "Quiz", to: "/pulse/quiz" },
          { label: quiz.data ? quizName(quiz.data) : "Chapter quiz" },
        ]}
      />
      <QueryView
        query={quiz}
        skeleton={
          <div className="flex flex-col gap-3">
            <Skeleton className="h-8 w-2/3" />
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-36 w-full" />
            ))}
          </div>
        }
      >
        {(data) =>
          data.submitted_at ? (
            <Results quiz={data} />
          ) : data.started_at ? (
            <Questions quiz={data} />
          ) : (
            <Intro quiz={data} />
          )
        }
      </QueryView>
    </div>
  );
}

function Intro({ quiz }: { quiz: QuizDetail }) {
  const tz = useTimezone();
  const start = useStartQuiz(quiz.id);
  const upcoming = quiz.state === "upcoming";
  return (
    <section className="flex flex-col items-start gap-4">
      <h1 className="text-2xl font-bold">{quizName(quiz)}</h1>
      <ul className="list-disc pl-5 text-ink-soft">
        {quiz.chapters.map((c) => (
          <li key={c.id}>
            {c.course_code} · Chapter {c.order}: {c.title}
          </li>
        ))}
      </ul>
      <p>
        {quiz.question_count} questions, about 10 minutes.{" "}
        {quiz.state === "open" && (
          <>
            Closes {formatExact(quiz.closes_at, tz)} (<TimeLeft closesAt={quiz.closes_at} />
            ).
          </>
        )}
        {quiz.state === "closed" &&
          "The window has closed, so this is practice and won't change your streak."}
        {upcoming && `Opens ${formatExact(quiz.opens_at, tz)}.`}
      </p>
      {!upcoming && (
        <Button
          pending={start.isPending}
          pendingLabel="Loading questions…"
          onClick={() => start.mutate(undefined, { onError: (e) => toast.error(errorMessage(e)) })}
        >
          {quiz.state === "closed" ? "Practice now" : "Start quiz"}
        </Button>
      )}
    </section>
  );
}

function Questions({ quiz }: { quiz: QuizDetail }) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const submit = useSubmitQuiz(quiz.id);
  const answered = Object.keys(answers).length;
  const total = quiz.questions.length;
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        submit.mutate(answers, { onError: (err) => toast.error(errorMessage(err)) });
      }}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold">{quizName(quiz)}</h1>
        {quiz.state === "open" && <TimeLeft closesAt={quiz.closes_at} />}
      </header>
      <ol className="flex flex-col gap-3">
        {quiz.questions.map((q) => (
          <li key={q.position}>
            <QuestionField
              index={q.position}
              prompt={q.prompt}
              options={q.options}
              value={answers[String(q.position)]}
              onChange={(v) => setAnswers({ ...answers, [String(q.position)]: v })}
              disabled={submit.isPending}
            />
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          disabled={answered < total}
          pending={submit.isPending}
          pendingLabel="Checking answers…"
        >
          Submit answers
        </Button>
        <span className="text-sm text-ink-soft" aria-live="polite">
          {answered} of {total} answered
        </span>
      </div>
    </form>
  );
}

function Results({ quiz }: { quiz: QuizDetail }) {
  const pct = Math.round((quiz.score ?? 0) * 100);
  const results = new Map((quiz.results ?? []).map((r) => [r.position, r]));
  const celebrate = Boolean(quiz.milestone);
  return (
    <section aria-labelledby="results" className="flex flex-col gap-4">
      <div className="relative flex flex-col items-center gap-3 rounded-lg border border-line bg-surface p-5 text-center sm:flex-row sm:text-left">
        <div className="relative">
          <Mascot
            mood={pct >= 60 ? "good" : "medium"}
            moment={celebrate ? { kind: "celebrate", key: `quiz-${quiz.id}` } : null}
            size={120}
          />
          <Confetti show={celebrate} />
        </div>
        <div className="flex flex-col gap-1">
          <h1 id="results" className="text-2xl font-bold">
            {pct}% correct{quiz.sharp ? " · Sharp" : ""}
          </h1>
          <p className="text-ink-soft" role="status">
            {quiz.counted_for_streak
              ? `Counted for your streak: ${quiz.streak} in a row.${quiz.milestone ? ` That's a ${quiz.milestone}-quiz milestone.` : ""}`
              : "Practice run. It doesn't change your streak."}
          </p>
        </div>
      </div>
      <ol className="flex flex-col gap-3">
        {quiz.questions.map((q) => {
          const r = results.get(q.position);
          return (
            <li key={q.position}>
              <QuestionField
                index={q.position}
                prompt={q.prompt}
                options={q.options}
                value={r?.chosen}
                disabled
                correctIndex={r?.correct}
                explanation={r?.explanation}
                footer={
                  r && (
                    <Link
                      to={`/lms/courses/${r.course_id}/chapters/${r.chapter_id}`}
                      className="self-start text-sm font-bold text-pine underline"
                    >
                      Review this in the chapter
                    </Link>
                  )
                }
              />
            </li>
          );
        })}
      </ol>
      <Link
        to="/pulse/quiz"
        className="inline-flex min-h-11 items-center self-start rounded-md bg-pine px-4 font-bold text-on-pine"
      >
        Back to quizzes
      </Link>
    </section>
  );
}

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Button, ErrorState, Skeleton } from "@/components/ui";
import { TODAY } from "@/features/auth/redirects";
import { useCancelJob, useGenerate, useLatestJob } from "@/features/pulse/api";
import { PlanProgress } from "@/features/pulse/PlanProgress";
import { PlanReview } from "@/features/pulse/PlanReview";
import { useQuizzes } from "@/features/quiz/api";
import { quizName } from "@/features/quiz/quizName";
import { formatExact, useTimezone } from "@/lib/time";
import { onboardingKey, useCompleteOnboarding } from "../api";
import type { StepProps } from "../stepTypes";

const CHANGES = [
  { step: 2, label: "Study time" },
  { step: 3, label: "Preferences" },
  { step: 4, label: "Reminders" },
];

export function ScheduleStep({ state, goTo, saving }: StepProps) {
  const client = useQueryClient();
  const job = useLatestJob();
  const generate = useGenerate();
  const cancel = useCancelJob();
  const started = useRef(false);
  const latest = job.data;
  const running = latest?.state === "queued" || latest?.state === "running";

  useEffect(() => {
    if (latest?.state === "done") {
      void client.invalidateQueries({ queryKey: onboardingKey });
      void client.invalidateQueries({ queryKey: ["pulse", "schedule"] });
      void client.invalidateQueries({ queryKey: ["quizzes"] });
    }
  }, [client, latest?.id, latest?.state]);

  useEffect(() => {
    if (state.schedule_ready || started.current || job.isPending || running) return;
    if (latest?.state === "cancelled") return;
    started.current = true;
    generate.mutate(undefined);
  }, [state.schedule_ready, job.isPending, running, latest?.state, generate]);

  const regenerate = () => generate.mutate(undefined);

  if (generate.isError)
    return (
      <div className="flex flex-col items-start gap-3">
        <ErrorState
          message={`Building the schedule failed: ${errorMessage(generate.error)} Your answers are saved.`}
          onRetry={regenerate}
          retrying={generate.isPending}
        />
        <Button variant="secondary" onClick={() => goTo(2)} disabled={saving}>
          Change study time
        </Button>
      </div>
    );
  if (latest && running)
    return (
      <PlanProgress
        job={latest}
        onCancel={() => cancel.mutate(latest.id)}
        cancelling={cancel.isPending}
      />
    );
  if (latest?.state === "failed" && !state.schedule_ready)
    return (
      <ErrorState
        message="Building the schedule failed. Your answers are saved."
        onRetry={regenerate}
        retrying={generate.isPending}
      />
    );
  if (latest?.state === "cancelled" && !state.schedule_ready)
    return (
      <div className="flex flex-col items-start gap-3">
        <p>You cancelled the last run.</p>
        <Button onClick={regenerate} pending={generate.isPending} pendingLabel="Starting…">
          Build my schedule
        </Button>
      </div>
    );
  if (!state.schedule_ready) return <Skeleton className="h-64 w-full" />;
  return <Review goTo={goTo} saving={saving} />;
}

function Review({ goTo, saving }: Pick<StepProps, "goTo" | "saving">) {
  const navigate = useNavigate();
  const complete = useCompleteOnboarding();
  const [changing, setChanging] = useState(false);
  return (
    <section aria-label="Review your schedule" className="flex flex-col gap-5">
      <PlanReview onAddTime={() => goTo(2)} />
      <FirstQuiz />
      <div className="flex flex-col gap-3 border-t border-line pt-4">
        {complete.isError && (
          <p role="alert" className="text-sm font-bold text-berry">
            {errorMessage(complete.error)}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() =>
              complete.mutate(undefined, {
                onSuccess: () => navigate(TODAY, { replace: true }),
              })
            }
            pending={complete.isPending}
            pendingLabel="Finishing…"
            disabled={saving}
          >
            Looks good
          </Button>
          <Button
            variant="secondary"
            aria-expanded={changing}
            onClick={() => setChanging((v) => !v)}
            disabled={complete.isPending}
          >
            Change something
          </Button>
        </div>
        {changing && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-ink-soft">
              Pick what to change. Your schedule is rebuilt when you come back here.
            </p>
            <div className="flex flex-wrap gap-2">
              {CHANGES.map((c) => (
                <Button
                  key={c.step}
                  size="sm"
                  variant="ghost"
                  onClick={() => goTo(c.step)}
                  disabled={saving}
                >
                  {c.label}
                </Button>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function FirstQuiz() {
  const tz = useTimezone();
  const open = useQuizzes("open");
  const upcoming = useQuizzes("upcoming");
  if (open.isPending || upcoming.isPending) return <Skeleton className="h-16 w-full" />;
  const first = [...(open.data ?? []), ...(upcoming.data ?? [])].sort(
    (a, b) => Date.parse(a.opens_at) - Date.parse(b.opens_at),
  )[0];
  return (
    <section aria-labelledby="first-quiz" className="rounded-lg border border-line bg-surface p-4">
      <h2 id="first-quiz" className="mb-1 font-bold">
        Your first chapter quiz
      </h2>
      {first ? (
        <p className="text-sm">
          {quizName(first)} opens {formatExact(first.opens_at, tz)} and closes{" "}
          {formatExact(first.closes_at, tz)}. Finish it in time to start your streak.
        </p>
      ) : (
        <p className="text-sm text-ink-soft">
          Quizzes open on the day your plan gives you a chapter. None are scheduled yet.
        </p>
      )}
    </section>
  );
}

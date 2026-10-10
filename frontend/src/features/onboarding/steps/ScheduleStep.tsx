import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Button, ErrorState, Skeleton } from "@/components/ui";
import { TODAY } from "@/features/auth/redirects";
import { useCancelJob, useGenerate, useLatestJob } from "@/features/pulse/api";
import { PlanProgress } from "@/features/pulse/PlanProgress";
import { PlanReview } from "@/features/pulse/PlanReview";
import { useTodayDeck } from "@/features/quiz/api";
import { focusLine } from "@/features/quiz/topics";
import { useTimezone } from "@/lib/time";
import { onboardingKey, useCompleteOnboarding } from "../api";
import type { StepProps } from "../stepTypes";
import { YourChoices } from "./YourChoices";

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
      void client.invalidateQueries({ queryKey: ["decks"] });
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
  return <Review state={state} goTo={goTo} saving={saving} />;
}

function Review({ state, goTo, saving }: Pick<StepProps, "state" | "goTo" | "saving">) {
  const navigate = useNavigate();
  const complete = useCompleteOnboarding();
  return (
    <section aria-label="Review your schedule" className="flex flex-col gap-5">
      <YourChoices state={state} goTo={goTo} disabled={saving || complete.isPending} />
      <PlanReview onAddTime={() => goTo(2)} />
      <DailyCards />
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
        </div>
        <p className="text-sm text-ink-soft">
          Changing an answer rebuilds your schedule when you come back to this step.
        </p>
      </div>
    </section>
  );
}

function DailyCards() {
  const tz = useTimezone();
  const today = useTodayDeck();
  if (today.isPending) return <Skeleton className="h-16 w-full" />;
  return (
    <section aria-labelledby="daily-cards" className="rounded-lg border border-line bg-surface p-4">
      <h2 id="daily-cards" className="mb-1 font-bold">
        Daily flashcards
      </h2>
      <p className="text-sm">
        Each day you get a short deck from your courses, about 3 minutes. Finish it before midnight
        to keep your streak going.
      </p>
      {today.data && (
        <p className="mt-1 text-sm font-bold text-pine">Today: {focusLine(today.data.focus, tz)}</p>
      )}
    </section>
  );
}

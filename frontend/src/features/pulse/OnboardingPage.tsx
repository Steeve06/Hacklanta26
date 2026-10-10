import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, errorMessage, unwrap } from "@/api/client";
import { Button, ErrorState, QueryView, Skeleton, Textarea, toast } from "@/components/ui";
import { meKey, useMe, useUpdateMe, type Me } from "@/features/auth/hooks";
import { useCourses } from "@/features/lms/api";
import { cx } from "@/lib/cx";
import {
  useAvailability,
  useCancelJob,
  useGenerate,
  useLatestJob,
  useSaveAvailability,
  type AvailabilityBlock,
} from "./api";
import { AvailabilityEditor } from "./AvailabilityEditor";
import { totalHours } from "./availability";
import { BlackoutsEditor } from "./BlackoutsEditor";
import { PlanProgress } from "./PlanProgress";
import { PreferencesFields, type Preferences } from "./PreferencesFields";
import { preferenceErrors } from "./preferences";
import { PlanReview } from "./PlanReview";

const STEPS = ["Courses", "Availability", "Preferences", "Your schedule"];

export function OnboardingPage() {
  const me = useMe();
  const availability = useAvailability();
  if (me.isPending || availability.isPending) return <Skeleton className="h-96 w-full" />;
  if (me.isError)
    return <ErrorState message={errorMessage(me.error)} onRetry={() => void me.refetch()} />;
  if (me.data.profile?.onboarding_done) return <Navigate to="/pulse" replace />;
  return <Wizard me={me.data} initialBlocks={availability.data?.blocks ?? []} />;
}

function Wizard({ me, initialBlocks }: { me: Me; initialBlocks: AvailabilityBlock[] }) {
  const latestJob = useLatestJob();
  const jobInFlight =
    latestJob.data && ["queued", "running", "done"].includes(latestJob.data.state);
  const [step, setStep] = useState(jobInFlight ? 3 : 0);
  const [blocks, setBlocks] = useState<AvailabilityBlock[]>(initialBlocks);
  const profile = me.profile;
  const [prefs, setPrefs] = useState<Preferences>({
    max_hours_per_day: String(profile?.max_hours_per_day ?? "3"),
    session_minutes: profile?.session_minutes ?? 50,
    earliest_time: profile?.earliest_time ?? "08:00",
    latest_time: profile?.latest_time ?? "22:00",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || me.timezone,
    sass_level: profile?.sass_level ?? 3,
  });
  const saveAvailability = useSaveAvailability();
  const updateMe = useUpdateMe();
  const generate = useGenerate();

  async function startGenerating() {
    try {
      await saveAvailability.mutateAsync(blocks);
      await updateMe.mutateAsync({
        timezone: prefs.timezone,
        profile: {
          max_hours_per_day: prefs.max_hours_per_day,
          session_minutes: prefs.session_minutes as 25 | 50 | 90,
          earliest_time: prefs.earliest_time,
          latest_time: prefs.latest_time,
          sass_level: prefs.sass_level,
        },
      });
      await generate.mutateAsync(undefined);
      setStep(3);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const saving = saveAvailability.isPending || updateMe.isPending || generate.isPending;

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-3">
        <h1 className="text-2xl font-bold">Let's build your study plan</h1>
        <ol className="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Steps">
          {STEPS.map((name, i) => (
            <li
              key={name}
              aria-current={i === step ? "step" : undefined}
              className={cx(
                "flex items-center gap-2",
                i === step
                  ? "font-bold text-ink"
                  : i < step
                    ? "text-pine-strong"
                    : "text-ink-faint",
              )}
            >
              <span
                className={cx(
                  "flex h-6 w-6 items-center justify-center rounded-full border-2 text-xs",
                  i <= step ? "border-pine" : "border-line",
                  i < step && "bg-pine text-on-pine",
                )}
              >
                {i + 1}
              </span>
              {name}
            </li>
          ))}
        </ol>
      </header>

      {step === 0 && <CoursesStep onNext={() => setStep(1)} />}

      {step === 1 && (
        <section aria-labelledby="availability-step" className="flex flex-col gap-4">
          <div>
            <h2 id="availability-step" className="text-xl font-bold">
              When can you study each week?
            </h2>
            <p className="text-ink-soft">
              Add the times that are usually free. Pulse only schedules inside them.
            </p>
          </div>
          <AvailabilityEditor value={blocks} onChange={setBlocks} />
          <p className="text-sm font-bold" aria-live="polite">
            {totalHours(blocks).toFixed(1).replace(".0", "")} hours a week
          </p>
          <details className="rounded-lg border border-line bg-surface p-4">
            <summary className="min-h-11 cursor-pointer py-2 font-bold">
              Block off specific dates (work shifts, trips)
            </summary>
            <div className="pt-2">
              <BlackoutsEditor />
            </div>
          </details>
          <StepButtons
            onBack={() => setStep(0)}
            onNext={() => setStep(2)}
            nextDisabled={blocks.length === 0}
            nextHint={blocks.length === 0 ? "Add at least one block to continue." : undefined}
          />
        </section>
      )}

      {step === 2 && (
        <section aria-labelledby="prefs-step" className="flex flex-col gap-4">
          <h2 id="prefs-step" className="text-xl font-bold">
            How do you like to study?
          </h2>
          <PreferencesFields value={prefs} onChange={setPrefs} />
          <StepButtons
            onBack={() => setStep(1)}
            onNext={() => void startGenerating()}
            nextLabel="Generate my schedule"
            nextDisabled={Object.keys(preferenceErrors(prefs)).length > 0}
            pending={saving}
          />
        </section>
      )}

      {step === 3 && <GenerateStep onEdit={() => setStep(1)} />}
    </div>
  );
}

function CoursesStep({ onNext }: { onNext: () => void }) {
  const courses = useCourses();
  return (
    <section aria-labelledby="courses-step" className="flex flex-col gap-4">
      <div>
        <h2 id="courses-step" className="text-xl font-bold">
          Check your courses
        </h2>
        <p className="text-ink-soft">
          Your plan covers every chapter, assignment, discussion and quiz in these.
        </p>
      </div>
      <QueryView
        query={courses}
        skeleton={<Skeleton className="h-32 w-full" />}
        isEmpty={(d) => d.length === 0}
        empty={{
          title: "You aren't enrolled in any courses",
          body: "Ask your instructor to add you, then come back.",
        }}
      >
        {(data) => (
          <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
            {data.map((c) => (
              <li key={c.id} className="flex items-center gap-3 px-4 py-3">
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
      <StepButtons
        onNext={onNext}
        nextLabel="These are right"
        nextDisabled={!courses.data?.length}
      />
    </section>
  );
}

function GenerateStep({ onEdit }: { onEdit: () => void }) {
  const job = useLatestJob();
  const cancel = useCancelJob();
  const generate = useGenerate();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const accept = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PATCH("/api/v1/me/profile", { body: { profile: { onboarding_done: true } } }),
      ),
    onSuccess: (me) => {
      client.setQueryData(meKey, me);
      navigate("/pulse", { replace: true });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (job.isPending) return <Skeleton className="h-64 w-full" />;
  const data = job.data;
  if (!data || data.state === "cancelled") {
    return (
      <div className="flex flex-col items-start gap-3">
        <p>{data ? "You cancelled the last run." : "Nothing has been generated yet."}</p>
        <Button onClick={() => generate.mutate(undefined)} pending={generate.isPending}>
          Generate my schedule
        </Button>
        <Button variant="ghost" onClick={onEdit}>
          Change availability
        </Button>
      </div>
    );
  }
  if (data.state === "queued" || data.state === "running") {
    return (
      <PlanProgress
        job={data}
        onCancel={() => cancel.mutate(data.id)}
        cancelling={cancel.isPending}
      />
    );
  }
  if (data.state === "failed") {
    return (
      <ErrorState
        message="Building the schedule failed. Try again."
        onRetry={() => generate.mutate(undefined)}
        retrying={generate.isPending}
      />
    );
  }
  return (
    <section aria-labelledby="review" className="flex flex-col gap-5">
      <h2 id="review" className="text-xl font-bold">
        Here's your schedule
      </h2>
      <PlanReview />
      <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
        <Textarea
          label="Want changes? Tell Pulse what to adjust"
          placeholder="Less on weekends, more mornings"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          rows={2}
          maxLength={300}
        />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => accept.mutate()} pending={accept.isPending} pendingLabel="Saving…">
            Accept schedule
          </Button>
          <Button
            variant="secondary"
            disabled={!feedback.trim()}
            pending={generate.isPending}
            onClick={() =>
              generate.mutate(feedback, { onError: (err) => toast.error(errorMessage(err)) })
            }
          >
            Regenerate with changes
          </Button>
          <Button variant="ghost" onClick={onEdit}>
            Change availability
          </Button>
        </div>
      </div>
    </section>
  );
}

function StepButtons({
  onBack,
  onNext,
  nextLabel = "Continue",
  nextDisabled,
  nextHint,
  pending,
}: {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  nextHint?: string;
  pending?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {onBack && (
          <Button variant="ghost" onClick={onBack} disabled={pending}>
            Back
          </Button>
        )}
        <Button onClick={onNext} disabled={nextDisabled} pending={pending} pendingLabel="Saving…">
          {nextLabel}
        </Button>
      </div>
      {nextHint && <p className="text-sm text-ink-soft">{nextHint}</p>}
    </div>
  );
}

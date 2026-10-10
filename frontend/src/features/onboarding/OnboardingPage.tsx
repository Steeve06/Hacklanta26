import { useEffect, useRef } from "react";
import { MascotStill } from "@/components/mascot/MascotStill";
import { QueryView, Skeleton } from "@/components/ui";
import { cx } from "@/lib/cx";
import { useOnboarding, useSaveStep, type OnboardingState } from "./api";
import { AvailabilityStep } from "./steps/AvailabilityStep";
import { CoursesStep } from "./steps/CoursesStep";
import { NotificationsStep } from "./steps/NotificationsStep";
import { PreferencesStep } from "./steps/PreferencesStep";
import { ScheduleStep } from "./steps/ScheduleStep";
import { STEP_NAMES } from "./stepTypes";

const MASCOT_LINES = [
  "Hi, I'm Leon. I'll be keeping an eye on these courses for you. Closely.",
  "When are you actually free? Be honest. I'll find out anyway.",
  "Sprints or marathons? No judgement. Mostly.",
  "How much attitude can you handle in your reminders?",
  "Here's the plan. I worked very hard on it.",
];

export function OnboardingPage() {
  const state = useOnboarding();
  return (
    <QueryView query={state} skeleton={<Skeleton className="h-[32rem] w-full" />}>
      {(data) => <Wizard state={data} />}
    </QueryView>
  );
}

function Wizard({ state }: { state: OnboardingState }) {
  const save = useSaveStep();
  const heading = useRef<HTMLHeadingElement>(null);
  const step = state.step;
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    heading.current?.focus();
  }, [step]);

  const goTo = (target: number) => save.mutate({ step: target });
  const submit = (data: Record<string, unknown>) => save.mutate({ step, data });
  const props = { state, saving: save.isPending, submit, goTo, error: save.error };

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <p className="text-sm font-bold text-ink-soft">
          Step {step} of {STEP_NAMES.length}
        </p>
        <ol className="grid grid-cols-5 gap-1" aria-label="Onboarding steps">
          {STEP_NAMES.map((name, i) => (
            <li key={name} className="flex flex-col gap-1">
              <span
                aria-hidden="true"
                className={cx(
                  "h-1.5 rounded-full",
                  i + 1 < step || state.completed_steps.includes(i + 1)
                    ? "bg-pine"
                    : i + 1 === step
                      ? "bg-ink"
                      : "bg-line",
                )}
              />
              <span
                className={cx(
                  "hidden text-xs sm:block",
                  i + 1 === step ? "font-bold text-ink" : "text-ink-soft",
                )}
              >
                {name}
              </span>
              <span className="sr-only">
                {i + 1 === step
                  ? "(current step)"
                  : state.completed_steps.includes(i + 1)
                    ? "(done)"
                    : ""}
              </span>
            </li>
          ))}
        </ol>
        <div className="flex items-center gap-3">
          <MascotStill mood="good" size={44} />
          <p className="text-ink-soft">{MASCOT_LINES[step - 1]}</p>
        </div>
        <h1 ref={heading} tabIndex={-1} className="text-2xl font-bold outline-none">
          {STEP_NAMES[step - 1]}
        </h1>
      </header>
      {step === 1 && <CoursesStep key={`1-${state.version}`} {...props} />}
      {step === 2 && <AvailabilityStep key={stepKey(state)} {...props} />}
      {step === 3 && <PreferencesStep key={stepKey(state)} {...props} />}
      {step === 4 && <NotificationsStep key={stepKey(state)} {...props} />}
      {step === 5 && <ScheduleStep {...props} />}
    </div>
  );
}

/** Steps keep their own form state; a save from another tab remounts them with fresh data. */
function stepKey(state: OnboardingState): string {
  return `${state.step}-${state.stale ? state.version : "local"}`;
}

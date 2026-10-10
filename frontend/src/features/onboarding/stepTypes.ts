import type { OnboardingState } from "./api";

export const STEP_NAMES = ["Courses", "Study time", "Preferences", "Reminders", "Your schedule"];

export type StepProps = {
  state: OnboardingState;
  saving: boolean;
  submit: (data: Record<string, unknown>) => void;
  goTo: (step: number) => void;
  error: unknown;
};

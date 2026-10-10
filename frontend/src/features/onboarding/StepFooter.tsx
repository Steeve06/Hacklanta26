import { errorMessage } from "@/api/client";
import { Button } from "@/components/ui";

export function StepFooter({
  onBack,
  onNext,
  nextLabel = "Next",
  nextDisabled = false,
  hint,
  saving,
  error,
}: {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  hint?: string;
  saving: boolean;
  error?: unknown;
}) {
  return (
    <div className="flex flex-col gap-2 border-t border-line pt-4">
      {Boolean(error) && (
        <p role="alert" className="text-sm font-bold text-berry">
          {errorMessage(error)}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {onBack && (
          <Button variant="secondary" onClick={onBack} disabled={saving}>
            Back
          </Button>
        )}
        <Button onClick={onNext} disabled={nextDisabled} pending={saving} pendingLabel="Saving…">
          {nextLabel}
        </Button>
      </div>
      {hint && <p className="text-sm text-ink-soft">{hint}</p>}
    </div>
  );
}

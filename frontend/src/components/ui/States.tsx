import type { ReactNode } from "react";
import { Button } from "./Button";

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-lg border border-dashed border-line px-4 py-6">
      <p className="font-display text-lg font-bold">{title}</p>
      {body && <p className="max-w-prose text-sm text-ink-soft">{body}</p>}
      {action}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  retrying,
}: {
  message: string;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-lg border border-berry/40 bg-berry-soft px-4 py-4"
    >
      <p className="text-sm font-bold text-ink">{message}</p>
      {onRetry && (
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          pending={retrying}
          pendingLabel="Retrying…"
        >
          Retry
        </Button>
      )}
    </div>
  );
}

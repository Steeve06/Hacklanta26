import { cx } from "@/lib/cx";

const labels: Record<string, { text: string; tone: string }> = {
  not_started: { text: "Not started", tone: "border-line text-ink-soft" },
  in_progress: { text: "In progress", tone: "border-mustard bg-mustard-soft text-mustard-ink" },
  submitted: { text: "Submitted", tone: "border-pine bg-pine-soft text-pine-strong" },
  late: { text: "Submitted late", tone: "border-mustard bg-mustard-soft text-mustard-ink" },
  missed: { text: "Missed", tone: "border-berry bg-berry-soft text-berry" },
  excused: { text: "Excused", tone: "border-line bg-sunken text-ink-soft" },
  graded: { text: "Graded", tone: "border-pine bg-pine-soft text-pine-strong" },
  overdue: { text: "Overdue", tone: "border-berry bg-berry-soft text-berry" },
};

export function StatusPill({
  status,
  overdue = false,
}: {
  status: string | null | undefined;
  overdue?: boolean;
}) {
  if (!status) return null;
  const entry = labels[overdue ? "overdue" : status] ?? {
    text: status,
    tone: "border-line text-ink-soft",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-bold",
        entry.tone,
      )}
    >
      {entry.text}
    </span>
  );
}

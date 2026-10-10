import { Link } from "react-router-dom";
import { DueTime } from "@/components/Time";
import { typeLabels } from "@/features/lms/labels";
import { useNow } from "@/lib/useNow";
import type { Deadline } from "./api";

export function DeadlineList({
  deadlines,
  empty = "Nothing due soon.",
}: {
  deadlines: Deadline[];
  empty?: string;
}) {
  const now = useNow();
  if (deadlines.length === 0) return <p className="text-sm text-ink-soft">{empty}</p>;
  return (
    <ul className="flex flex-col divide-y divide-line">
      {deadlines.map((d) => (
        <li key={d.id}>
          <Link
            to={`/lms/courses/${d.course}/assignments/${d.id}`}
            className="flex min-h-11 flex-col gap-0.5 py-2 hover:underline"
          >
            <span className="text-xs font-bold text-ink-soft">
              {d.course_code} · {typeLabels[d.type]} · {d.weight_pct}%
              {d.extended ? " · extended" : ""}
            </span>
            <span className="font-bold">{d.title}</span>
            <span className="text-sm">
              {new Date(d.due_at).getTime() < now ? (
                <>
                  <span className="font-bold text-berry">Overdue</span> ·{" "}
                  <DueTime iso={d.closes_at} prefix="Late window closes" />
                </>
              ) : (
                <DueTime iso={d.due_at} />
              )}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

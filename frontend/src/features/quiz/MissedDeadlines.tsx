import { Link } from "react-router-dom";
import { DueTime } from "@/components/Time";
import { formatExact, useTimezone } from "@/lib/time";
import type { Streak } from "./api";

type Missed = Streak["missed_deadlines"][number];

const EFFECT: Record<NonNullable<Missed["streak_result"]>, string> = {
  frozen: "Used a freeze",
  missed: "Reset your streak",
};

/** Coursework from the last week that passed its due date without a submission. Each one counts
 * against the streak once; the study plan doesn't chase it. */
export function MissedDeadlines({ items }: { items: Missed[] }) {
  const tz = useTimezone();
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="missed-heading" className="flex flex-col gap-2">
      <h3 id="missed-heading" className="text-sm font-bold">
        Missed deadlines this week
      </h3>
      <ul className="flex flex-col gap-2 text-sm">
        {items.map((m) => (
          <li key={m.assessment_id} className="flex flex-col gap-0.5 border-l-2 border-berry pl-3">
            <span>
              <span className="font-bold">{m.course_code}</span> {m.title}
            </span>
            <span className="text-ink-soft">
              <DueTime iso={m.due_at} prefix="Was due" />
              {m.streak_result && ` · ${EFFECT[m.streak_result]}`}
            </span>
            {m.late_until && (
              <Link
                to={`/lms/courses/${m.course_id}/assignments/${m.assessment_id}`}
                className="font-bold text-pine-strong underline"
              >
                Submit late until {formatExact(m.late_until, tz)}
              </Link>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

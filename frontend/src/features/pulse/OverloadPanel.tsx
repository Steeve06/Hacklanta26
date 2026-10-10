import { Link } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { DueTime } from "@/components/Time";
import { useNow } from "@/lib/useNow";
import type { OverloadReport } from "./api";

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

/** A quiet note when some work won't fully fit in the student's study time. The plan is a help,
 * not a verdict, so it stays closed until opened. Only "no study time at all" is an alert.
 * `soonOnly` limits it to work due in the next 7 days (and hides it when there's none).
 * `onAddTime` replaces the link to Settings, e.g. to jump back to a step in onboarding. */
export function OverloadPanel({
  report,
  onAddTime,
  soonOnly = false,
}: {
  report: OverloadReport;
  onAddTime?: () => void;
  soonOnly?: boolean;
}) {
  const now = useNow();
  const linkClass = "inline-flex min-h-11 items-center font-bold text-pine-strong underline";
  const addTime = onAddTime ? (
    <button type="button" onClick={onAddTime} className={`${linkClass} self-start`}>
      Change study time
    </button>
  ) : (
    <Link to="/settings#availability" className={`${linkClass} self-start`}>
      Change study time
    </Link>
  );

  if (report.unresolvable && report.items.length === 0) {
    return (
      <section
        role="alert"
        className="flex flex-col gap-2 rounded-lg border-2 border-berry bg-berry-soft p-4"
      >
        <h2 className="text-lg font-bold">You have no study time set</h2>
        <p>Leon can't place anything until you add at least one weekly block.</p>
        {addTime}
      </section>
    );
  }

  const items = soonOnly
    ? report.items.filter((i) => Date.parse(i.due_at) - now <= WEEK_MS)
    : report.items;
  if (items.length === 0) return null;
  const count = items.length === 1 ? "1 item" : `${items.length} items`;

  return (
    <details className="group rounded-lg border border-line border-l-4 border-l-mustard bg-surface">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-4 py-2 [&::-webkit-details-marker]:hidden">
        <span>
          <span className="font-bold">
            {count} won't fully fit before {items.length === 1 ? "it's" : "they're"} due
          </span>
          <span className="block text-sm text-ink-soft">
            Your plan covers what it can. Open for details.
          </span>
        </span>
        <Icon name="chevron" className="h-5 w-5 shrink-0 text-ink-faint group-open:rotate-90" />
      </summary>
      <div className="flex flex-col gap-3 border-t border-line px-4 pb-4 pt-3">
        <ul className="flex flex-col gap-1 text-sm">
          {items.slice(0, 5).map((item) => (
            <li
              key={`${item.source_type}-${item.source_id}`}
              className="flex flex-wrap justify-between gap-2"
            >
              <span>
                <span className="font-bold">{item.course_code}</span> {item.title}
                {item.needs_longer_block && " (needs one longer block)"}
              </span>
              <span className="text-ink-soft">
                {Math.round(item.minutes_short)} min short · <DueTime iso={item.due_at} />
              </span>
            </li>
          ))}
          {items.length > 5 && <li className="text-ink-soft">and {items.length - 5} more</li>}
        </ul>
        {report.suggestions.length > 0 && (
          <div>
            <h3 className="text-sm font-bold">What would help</h3>
            <ul className="list-disc pl-5 text-sm">
              {report.suggestions.map((s) => (
                <li key={s.text}>{s.text}</li>
              ))}
            </ul>
          </div>
        )}
        {addTime}
      </div>
    </details>
  );
}

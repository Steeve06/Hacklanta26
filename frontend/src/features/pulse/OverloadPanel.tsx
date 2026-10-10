import { Link } from "react-router-dom";
import { DueTime } from "@/components/Time";
import type { OverloadReport } from "./api";

export function OverloadPanel({ report }: { report: OverloadReport }) {
  if (report.unresolvable && report.items.length === 0) {
    return (
      <section
        role="alert"
        className="flex flex-col gap-2 rounded-lg border-2 border-berry bg-berry-soft p-4"
      >
        <h2 className="text-lg font-bold">You have no study time set</h2>
        <p>Pulse can't place anything until you add at least one weekly block.</p>
        <Link to="/pulse/settings#availability" className="self-start font-bold text-ink underline">
          Add study time
        </Link>
      </section>
    );
  }
  return (
    <section
      aria-labelledby="overload-heading"
      className="flex flex-col gap-3 rounded-lg border-2 border-berry bg-berry-soft p-4"
    >
      <h2 id="overload-heading" className="text-lg font-bold">
        Not everything fits
      </h2>
      <p>
        You'd need about <strong>{report.extra_hours_needed} more hours</strong> to finish these on
        time:
      </p>
      <ul className="flex flex-col gap-1 text-sm">
        {report.items.slice(0, 5).map((item) => (
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
        {report.items.length > 5 && (
          <li className="text-ink-soft">and {report.items.length - 5} more</li>
        )}
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
      <Link
        to="/pulse/settings#availability"
        className="inline-flex min-h-11 items-center self-start rounded-md bg-ink px-4 font-bold text-paper"
      >
        Add study time
      </Link>
    </section>
  );
}

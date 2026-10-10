import { QueryView, Skeleton } from "@/components/ui";
import { formatDay, localDateKey, useTimezone } from "@/lib/time";
import { useNow } from "@/lib/useNow";
import { useSchedule } from "./api";
import { courseLookup } from "./courseColors";
import { OverloadPanel } from "./OverloadPanel";
import { SessionItem } from "./SessionItem";

export function PlanReview() {
  const schedule = useSchedule("overall");
  const tz = useTimezone();
  const now = useNow();
  return (
    <QueryView query={schedule} skeleton={<Skeleton className="h-64 w-full" />}>
      {(data) => {
        const course = courseLookup(data);
        const weekAhead = now + 7 * 86_400_000;
        const soon = data.sessions.filter(
          (s) => s.status === "planned" && new Date(s.start).getTime() < weekAhead,
        );
        const days = [...new Set(soon.map((s) => localDateKey(s.start, tz)))];
        return (
          <div className="flex flex-col gap-4">
            <p className="max-w-prose text-lg">{data.summary}</p>
            {data.overload_report && <OverloadPanel report={data.overload_report} />}
            <h3 className="text-lg font-bold">The next seven days</h3>
            {days.length === 0 ? (
              <p className="text-ink-soft">No sessions in the next week.</p>
            ) : (
              days.map((day) => {
                const sessions = soon.filter((s) => localDateKey(s.start, tz) === day);
                return (
                  <section
                    key={day}
                    aria-label={formatDay(sessions[0]?.start ?? day, tz)}
                    className="flex flex-col gap-2"
                  >
                    <h4 className="font-bold">{formatDay(sessions[0]?.start ?? day, tz)}</h4>
                    <div className="flex flex-col gap-2">
                      {sessions.map((s) => (
                        <SessionItem
                          key={s.id}
                          session={s}
                          color={course(s.course).color}
                          actions={false}
                        />
                      ))}
                    </div>
                  </section>
                );
              })
            )}
          </div>
        );
      }}
    </QueryView>
  );
}

import { Link } from "react-router-dom";
import { Card, QueryView, Skeleton } from "@/components/ui";
import { formatExact, useTimezone } from "@/lib/time";
import { useChecks, useStreak, type Check } from "./api";
import { OpenCheckRow } from "./CheckRow";
import { MissedDeadlines } from "./MissedDeadlines";
import { formatPlainDay } from "./plainDay";
import { StreakBadge, WeekStrip } from "./StreakBadge";

export function QuizHubPage() {
  const streak = useStreak();
  const open = useChecks("open");
  const upcoming = useChecks("upcoming");
  const past = useChecks("past");
  const tz = useTimezone();
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Study checks</h1>
        <p className="text-ink-soft">
          On each day your schedule gives you a chapter, a check opens: four timed cards on what you
          studied. Get three right before the end of the next day to keep your streak. Miss and you
          get one more try with new cards.
        </p>
      </header>
      <Card aria-labelledby="streak-heading">
        <h2 id="streak-heading" className="sr-only">
          Your streak
        </h2>
        <QueryView query={streak} skeleton={<Skeleton className="h-16 w-64" />}>
          {(data) => (
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <StreakBadge streak={data} />
                <dl className="flex gap-6 text-sm">
                  <div>
                    <dt className="text-ink-soft">Next milestone</dt>
                    <dd className="font-bold">
                      {data.next_milestone ? `${data.next_milestone} checks` : "All reached"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-soft">Next freeze in</dt>
                    <dd className="font-bold">
                      {data.freezes >= 2
                        ? "Full (2 saved)"
                        : `${data.toward_next_freeze} ${data.toward_next_freeze === 1 ? "check" : "checks"}`}
                    </dd>
                  </div>
                </dl>
              </div>
              <WeekStrip week={data.week} />
              <p className="text-xs text-ink-soft">
                Every 5 checks in a row earns a freeze (up to 2). A freeze covers a missed check or
                a deadline that passes without a submission. Days without a check don&apos;t count
                either way.
              </p>
              <MissedDeadlines items={data.missed_deadlines} />
            </div>
          )}
        </QueryView>
      </Card>
      <section aria-labelledby="open-heading" className="flex flex-col gap-2">
        <h2 id="open-heading" className="text-lg font-bold">
          Open now
        </h2>
        <QueryView
          query={open}
          skeleton={<Skeleton className="h-16 w-full" />}
          isEmpty={(d) => d.length === 0}
          empty={{
            title: "Nothing open",
            body: "A check opens on the day your schedule gives you a chapter, or as soon as you mark one complete.",
          }}
        >
          {(data) => data.map((c) => <OpenCheckRow key={c.id} check={c} />)}
        </QueryView>
      </section>
      <section aria-labelledby="upcoming-heading">
        <h2 id="upcoming-heading" className="mb-1 text-lg font-bold">
          Coming up
        </h2>
        <QueryView
          query={upcoming}
          skeleton={<Skeleton className="h-16 w-full" />}
          isEmpty={(d) => d.length === 0}
          empty={{ title: "None scheduled", body: "Checks follow the chapters in your schedule." }}
        >
          {(data) => (
            <ul className="divide-y divide-line">
              {data.map((c) => (
                <li key={c.id} className="flex flex-wrap justify-between gap-2 py-2 text-sm">
                  <span className="font-bold">{c.title}</span>
                  <span className="text-ink-soft">Opens {formatExact(c.opens_at, tz)}</span>
                </li>
              ))}
            </ul>
          )}
        </QueryView>
      </section>
      <section aria-labelledby="past-heading">
        <h2 id="past-heading" className="mb-1 text-lg font-bold">
          Past checks
        </h2>
        <QueryView
          query={past}
          skeleton={<Skeleton className="h-24 w-full" />}
          isEmpty={(d) => d.length === 0}
          empty={{ title: "No past checks yet", body: "Checks you've taken show up here." }}
        >
          {(data) => (
            <ul className="divide-y divide-line">
              {data.map((c) => (
                <li key={c.id}>
                  <Link
                    to={`/pulse/checks/${c.id}`}
                    className="flex min-h-11 flex-wrap items-center justify-between gap-2 py-2 text-sm hover:underline"
                  >
                    <span className="font-bold">
                      {formatPlainDay(c.scheduled_date, {
                        weekday: "short",
                        month: "short",
                        day: "numeric",
                      })}{" "}
                      · {c.title}
                    </span>
                    <span className="text-ink-soft">{pastResult(c)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </QueryView>
      </section>
    </div>
  );
}

function pastResult(c: Check): string {
  const score = c.best_correct !== null ? `${c.best_correct} of ${c.card_count}` : "";
  if (c.state === "missed") return "Missed";
  if (c.passed && c.counted_for_streak) return `Passed · ${score}`;
  if (c.passed) return `Passed late · ${score}`;
  return `Not passed · ${score}`;
}

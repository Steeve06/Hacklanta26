import { Card, EmptyState, QueryView, Skeleton } from "@/components/ui";
import { formatShortDay, useTimezone } from "@/lib/time";
import { Link } from "react-router-dom";
import { useQuizzes, useStreak, type Quiz } from "./api";
import { OpenQuizRow, StreakBadge, UpcomingQuizRow } from "./QuizCards";
import { quizName } from "./quizName";

export function QuizHubPage() {
  const streak = useStreak();
  const open = useQuizzes("open");
  const upcoming = useQuizzes("upcoming");
  const closed = useQuizzes("closed");
  const tz = useTimezone();
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Quiz</h1>
        <p className="text-ink-soft">
          Each chapter gets a short quiz on the day you study it. Finish it by the end of the next
          day to grow your streak.
        </p>
      </header>
      <Card aria-labelledby="streak-heading">
        <h2 id="streak-heading" className="sr-only">
          Your streak
        </h2>
        <QueryView query={streak} skeleton={<Skeleton className="h-16 w-64" />}>
          {(data) => (
            <div className="flex flex-wrap items-center justify-between gap-4">
              <StreakBadge streak={data} />
              <dl className="flex gap-6 text-sm">
                <div>
                  <dt className="text-ink-soft">Next milestone</dt>
                  <dd className="font-bold">
                    {data.next_milestone ? `${data.next_milestone} in a row` : "All reached"}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-soft">Next freeze in</dt>
                  <dd className="font-bold">
                    {data.freezes >= 2
                      ? "Full (2 saved)"
                      : `${data.toward_next_freeze} ${data.toward_next_freeze === 1 ? "quiz" : "quizzes"}`}
                  </dd>
                </div>
              </dl>
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
            title: "No quiz is open",
            body: "Your next quiz opens on the day your plan gives you a chapter, or as soon as you mark a chapter complete.",
          }}
        >
          {(data) => (
            <div className="flex flex-col gap-2">
              {data.map((q) => (
                <OpenQuizRow key={q.id} quiz={q} />
              ))}
            </div>
          )}
        </QueryView>
      </section>
      <section aria-labelledby="upcoming-heading">
        <h2 id="upcoming-heading" className="mb-1 text-lg font-bold">
          Coming up
        </h2>
        <QueryView
          query={upcoming}
          skeleton={<Skeleton className="h-24 w-full" />}
          isEmpty={(d) => d.length === 0}
          empty={{ title: "Nothing scheduled yet" }}
        >
          {(data) => (
            <ul className="divide-y divide-line">
              {data.slice(0, 6).map((q) => (
                <UpcomingQuizRow key={q.id} quiz={q} />
              ))}
            </ul>
          )}
        </QueryView>
      </section>
      <section aria-labelledby="past-heading">
        <h2 id="past-heading" className="mb-1 text-lg font-bold">
          Past quizzes
        </h2>
        <QueryView
          query={closed}
          skeleton={<Skeleton className="h-24 w-full" />}
          isEmpty={(d) => d.length === 0}
          empty={{ title: "No past quizzes yet" }}
        >
          {(data) =>
            data.length === 0 ? (
              <EmptyState title="No past quizzes yet" />
            ) : (
              <ul className="divide-y divide-line">
                {data.map((q) => (
                  <li key={q.id}>
                    <Link
                      to={`/pulse/quiz/${q.id}`}
                      className="flex min-h-11 flex-wrap items-center justify-between gap-2 py-2 text-sm hover:underline"
                    >
                      <span className="font-bold">{quizName(q)}</span>
                      <span className="text-ink-soft">
                        Closed {formatShortDay(q.closes_at, tz)} · {pastResult(q)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )
          }
        </QueryView>
      </section>
    </div>
  );
}

function pastResult(q: Quiz): string {
  if (q.submitted_at) {
    const score = `${Math.round((q.score ?? 0) * 100)}%`;
    return q.counted_for_streak ? score : `${score} (practice)`;
  }
  if (q.streak_result === "frozen") return "Freeze used, streak kept · take it as practice";
  return "Missed · take it as practice";
}

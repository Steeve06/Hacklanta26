import { Link } from "react-router-dom";
import { Card, QueryView, Skeleton } from "@/components/ui";
import { useDecks, useStreak, useTodayDeck, type Deck } from "./api";
import { StreakBadge, WeekStrip } from "./StreakBadge";
import { TodayCard } from "./TodayCard";
import { formatDeckDay } from "./topics";

export function QuizHubPage() {
  const streak = useStreak();
  const today = useTodayDeck();
  const decks = useDecks();
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Daily flashcards</h1>
        <p className="text-ink-soft">
          Five quick flashcards a day from your courses. When a quiz or assignment is coming up, the
          deck helps you prepare for it; in quiet weeks it mixes in review. Finish today&apos;s deck
          to keep your streak going.
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
                      {data.next_milestone ? `${data.next_milestone} days` : "All reached"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-soft">Next freeze in</dt>
                    <dd className="font-bold">
                      {data.freezes >= 2
                        ? "Full (2 saved)"
                        : `${data.toward_next_freeze} ${data.toward_next_freeze === 1 ? "day" : "days"}`}
                    </dd>
                  </div>
                </dl>
              </div>
              <WeekStrip week={data.week} />
              <p className="text-xs text-ink-soft">
                Every 5 days in a row earns a freeze (up to 2). A freeze covers a day you miss.
              </p>
            </div>
          )}
        </QueryView>
      </Card>
      <section aria-labelledby="today-heading" className="flex flex-col gap-2">
        <h2 id="today-heading" className="text-lg font-bold">
          Today
        </h2>
        <QueryView query={today} skeleton={<Skeleton className="h-20 w-full" />}>
          {(deck) => <TodayCard deck={deck} />}
        </QueryView>
      </section>
      <section aria-labelledby="past-heading">
        <h2 id="past-heading" className="mb-1 text-lg font-bold">
          Past decks
        </h2>
        <QueryView
          query={decks}
          skeleton={<Skeleton className="h-24 w-full" />}
          isEmpty={(d) => d.filter((x) => x.state !== "open").length === 0}
          empty={{ title: "No past decks yet", body: "Your finished decks show up here." }}
        >
          {(data) => (
            <ul className="divide-y divide-line">
              {data
                .filter((d) => d.state !== "open")
                .map((d) => (
                  <li key={d.id}>
                    <Link
                      to={`/pulse/quiz/${d.id}`}
                      className="flex min-h-11 flex-wrap items-center justify-between gap-2 py-2 text-sm hover:underline"
                    >
                      <span className="font-bold">
                        {formatDeckDay(d.day, { weekday: "short", month: "short", day: "numeric" })}
                      </span>
                      <span className="text-ink-soft">{pastResult(d)}</span>
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

function pastResult(d: Deck): string {
  if (!d.completed_at) return "Not finished · open it to practise";
  const known = `${d.knew} of ${d.card_count} known`;
  return d.counted_for_streak ? known : `${known} (practice)`;
}

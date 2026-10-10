import { Link } from "react-router-dom";
import { Card, EmptyState, QueryView, Skeleton } from "@/components/ui";
import { useMe } from "@/features/auth/hooks";
import { formatDay, useTimezone } from "@/lib/time";
import { useNow } from "@/lib/useNow";
import { useSchedule } from "./api";
import { courseLookup } from "./courseColors";
import { DeadlineList } from "./DeadlineList";
import { OverloadPanel } from "./OverloadPanel";
import { SessionItem } from "./SessionItem";
import { StatusPanel } from "./StatusPanel";
import { QuizAside } from "@/features/quiz/QuizAside";
import { SupportiveBanner } from "@/features/notifications/SupportiveBanner";

export function TodayPage() {
  const me = useMe();
  const tz = useTimezone();
  const now = useNow();
  const today = useSchedule("today");

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="flex flex-col gap-5">
        <header>
          <p className="text-sm font-bold text-ink-soft">{formatDay(new Date(now), tz)}</p>
          <h1 className="text-2xl font-bold md:text-3xl">Today, {me.data?.first_name}</h1>
        </header>
        <SupportiveBanner />
        <StatusPanel />
        <QueryView
          query={today}
          skeleton={
            <div className="flex flex-col gap-3">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          }
        >
          {(data) => {
            const course = courseLookup(data);
            const sessions = data.sessions.filter((s) => s.status !== "rescheduled");
            return (
              <>
                {data.overload_report && <OverloadPanel report={data.overload_report} soonOnly />}
                <section aria-labelledby="sessions-heading" className="flex flex-col gap-3">
                  <h2 id="sessions-heading" className="text-lg font-bold">
                    Your sessions
                  </h2>
                  {sessions.length === 0 ? (
                    <EmptyState
                      title="Nothing scheduled today"
                      body="Enjoy it. Your next sessions are in the week view."
                      action={
                        <Link to="/pulse/week" className="font-bold text-pine underline">
                          Open the week
                        </Link>
                      }
                    />
                  ) : (
                    <div className="flex flex-col gap-2">
                      {sessions.map((s) => (
                        <SessionItem key={s.id} session={s} color={course(s.course).color} />
                      ))}
                    </div>
                  )}
                </section>
              </>
            );
          }}
        </QueryView>
      </div>
      <aside className="flex flex-col gap-4">
        <QuizAside />
        <Card aria-labelledby="coming-up">
          <h2 id="coming-up" className="mb-1 text-lg font-bold">
            Coming up
          </h2>
          {today.data ? (
            <DeadlineList deadlines={today.data.upcoming} />
          ) : (
            <Skeleton className="h-40 w-full" />
          )}
        </Card>
        {today.data?.summary && (
          <Card aria-label="Plan summary">
            <h2 className="mb-1 text-base font-bold">Your schedule</h2>
            <p className="text-sm text-ink-soft">{today.data.summary}</p>
          </Card>
        )}
      </aside>
    </div>
  );
}

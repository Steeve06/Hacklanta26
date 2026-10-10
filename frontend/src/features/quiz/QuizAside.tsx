import { Card, Skeleton } from "@/components/ui";
import { useChecks, useStreak } from "./api";
import { OpenCheckRow } from "./CheckRow";
import { StreakBadge } from "./StreakBadge";

export function QuizAside() {
  const streak = useStreak();
  const open = useChecks("open");
  return (
    <Card aria-labelledby="quiz-aside">
      <h2 id="quiz-aside" className="sr-only">
        Streak and open study checks
      </h2>
      {streak.data ? (
        <StreakBadge streak={streak.data} compact />
      ) : (
        <Skeleton className="h-11 w-40" />
      )}
      <div className="mt-3 flex flex-col gap-2">
        {open.isPending ? (
          <Skeleton className="h-14 w-full" />
        ) : open.data?.length ? (
          open.data.map((c) => <OpenCheckRow key={c.id} check={c} />)
        ) : (
          <p className="text-sm text-ink-soft">
            No check open. One opens on each day your schedule gives you a chapter.
          </p>
        )}
      </div>
    </Card>
  );
}

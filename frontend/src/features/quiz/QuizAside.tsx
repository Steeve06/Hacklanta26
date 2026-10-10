import { Card, Skeleton } from "@/components/ui";
import { useStreak, useTodayDeck } from "./api";
import { StreakBadge } from "./StreakBadge";
import { TodayCard } from "./TodayCard";

export function QuizAside() {
  const streak = useStreak();
  const today = useTodayDeck();
  return (
    <Card aria-labelledby="quiz-aside">
      <h2 id="quiz-aside" className="sr-only">
        Streak and today&apos;s flashcards
      </h2>
      {streak.data ? (
        <StreakBadge streak={streak.data} compact />
      ) : (
        <Skeleton className="h-11 w-40" />
      )}
      <div className="mt-3">
        {today.data ? <TodayCard deck={today.data} /> : <Skeleton className="h-14 w-full" />}
      </div>
    </Card>
  );
}

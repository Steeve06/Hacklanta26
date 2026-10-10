import { Link } from "react-router-dom";
import { Card, Skeleton } from "@/components/ui";
import { useQuizzes, useStreak } from "./api";
import { OpenQuizRow, StreakBadge } from "./QuizCards";

export function QuizAside() {
  const streak = useStreak();
  const open = useQuizzes("open");
  return (
    <Card aria-labelledby="quiz-aside">
      <h2 id="quiz-aside" className="sr-only">
        Streak and open quizzes
      </h2>
      {streak.data ? (
        <StreakBadge streak={streak.data} compact />
      ) : (
        <Skeleton className="h-11 w-40" />
      )}
      <div className="mt-3 flex flex-col gap-2">
        {open.data?.length ? (
          open.data.map((q) => <OpenQuizRow key={q.id} quiz={q} />)
        ) : (
          <p className="text-sm text-ink-soft">
            No quiz open right now.{" "}
            <Link to="/pulse/quiz" className="font-bold text-pine underline">
              See upcoming
            </Link>
          </p>
        )}
      </div>
    </Card>
  );
}

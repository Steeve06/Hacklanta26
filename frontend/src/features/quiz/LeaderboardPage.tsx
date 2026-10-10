import { Link } from "react-router-dom";
import { Card, Skeleton } from "@/components/ui";
import { useLeaderboard, useStreak } from "./api";
import { Leaderboard } from "./Leaderboard";

/** This week's standings among classmates, with the student's own numbers on top. */
export function LeaderboardPage() {
  const board = useLeaderboard(null);
  const streak = useStreak();
  const me = board.data?.rows.find((r) => r.is_me);
  const people = board.data?.rows.length ?? 0;
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Leaderboard</h1>
        <p className="text-ink-soft">
          Study checks earn XP: 10 for each right answer and 20 for finishing a check. Standings
          reset every Monday.
        </p>
      </header>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Your rank" loading={board.isPending}>
          {me ? `${me.rank} of ${people}` : "–"}
        </Stat>
        <Stat label="XP this week" loading={board.isPending}>
          {me?.xp ?? 0}
        </Stat>
        <Stat label="Checks in a row" loading={streak.isPending}>
          {streak.data?.current ?? 0}
        </Stat>
        <Stat label="Next milestone" loading={streak.isPending}>
          {streak.data?.next_milestone ? `${streak.data.next_milestone} checks` : "All reached"}
        </Stat>
      </dl>
      <Leaderboard />
      <p className="text-sm text-ink-soft">
        To climb, finish your open{" "}
        <Link to="/pulse/checks" className="font-bold text-pine underline">
          study checks
        </Link>{" "}
        before they close.
      </p>
    </div>
  );
}

function Stat({
  label,
  loading,
  children,
}: {
  label: string;
  loading: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card className="flex flex-col gap-1 p-4">
      <dt className="text-sm text-ink-soft">{label}</dt>
      <dd className="font-display text-2xl font-extrabold tabular-nums">
        {loading ? <Skeleton className="h-8 w-16" /> : children}
      </dd>
    </Card>
  );
}

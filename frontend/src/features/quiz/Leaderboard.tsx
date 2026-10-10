import { useState } from "react";
import { Icon } from "@/components/Icon";
import { ChipGroup, QueryView, Skeleton } from "@/components/ui";
import { cx } from "@/lib/cx";
import { keyLabel } from "@/lib/time";
import { useLeaderboard, type LeaderboardRow } from "./api";

const RANK_STYLES = ["bg-mustard text-ink", "bg-sunken text-ink", "bg-berry-soft text-berry"];

/** This week's XP from study checks among the student's classmates, filterable by course. */
export function Leaderboard() {
  const [course, setCourse] = useState("all");
  const query = useLeaderboard(course === "all" ? null : Number(course));
  return (
    <section
      aria-labelledby="leaderboard-heading"
      className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-4 md:p-5"
    >
      <header className="flex flex-col gap-1">
        <h2 id="leaderboard-heading" className="font-display text-2xl font-extrabold">
          Leaderboard
        </h2>
        <p className="text-sm text-ink-soft">
          {query.data
            ? `XP from study checks since ${keyLabel(query.data.week_start, { weekday: "short", month: "short", day: "numeric" })}. Resets every Monday.`
            : "This week's XP. Resets every Monday."}
        </p>
      </header>
      {query.data && query.data.courses.length > 1 && (
        <ChipGroup
          label="Which classmates"
          value={course}
          onChange={setCourse}
          options={[
            { value: "all", label: "All my classes" },
            ...query.data.courses.map((c) => ({ value: String(c.id), label: c.code })),
          ]}
        />
      )}
      <QueryView query={query} skeleton={<Skeleton className="h-64 w-full" />}>
        {(data) => (
          <>
            <ol className="flex flex-col gap-1" aria-label="Rankings">
              {data.rows.map((row) => (
                <Row key={row.student_id} row={row} />
              ))}
            </ol>
            {data.rows.every((r) => r.xp === 0) && (
              <p className="text-sm text-ink-soft">
                Nobody has scored this week yet. Finish a study check to take the top spot.
              </p>
            )}
          </>
        )}
      </QueryView>
    </section>
  );
}

function Row({ row }: { row: LeaderboardRow }) {
  return (
    <li
      aria-current={row.is_me ? "true" : undefined}
      className={cx(
        "flex min-h-12 items-center gap-3 rounded-md px-3 py-2",
        row.is_me ? "border-2 border-mustard bg-mustard-soft" : "border border-transparent",
      )}
    >
      <span
        className={cx(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-display font-extrabold",
          RANK_STYLES[row.rank - 1] ?? "text-ink-soft",
        )}
      >
        {row.rank}
      </span>
      <span className="min-w-0 flex-1 truncate font-bold">
        {row.name}
        {row.is_me && <span className="ml-1 font-normal text-ink-soft">(you)</span>}
      </span>
      <span
        className="flex items-center gap-1 text-sm text-ink-soft"
        title={`${row.streak} checks in a row`}
      >
        <Icon name="flame" className={cx("h-4 w-4", row.streak ? "text-mustard-ink" : "")} />
        {row.streak}
        <span className="sr-only"> checks in a row</span>
      </span>
      <span className="w-20 text-right font-display text-lg font-extrabold tabular-nums">
        {row.xp}
        <span className="ml-1 text-xs font-bold text-ink-soft">XP</span>
      </span>
    </li>
  );
}

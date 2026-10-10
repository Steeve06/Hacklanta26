import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Button, toast } from "@/components/ui";
import { cx } from "@/lib/cx";
import { formatTime, useTimezone } from "@/lib/time";
import { useNow } from "@/lib/useNow";
import { useRescheduleSession, useUpdateSession, type Session } from "./api";
import { sessionLink } from "./sessionLink";

const kindLabel: Record<string, string> = {
  study: "Reading",
  assignment: "Assignment",
  discussion: "Discussion",
  quiz: "Quiz",
  chapter_quiz: "Study check",
};

const statusLabel: Record<string, string> = {
  done: "Done",
  partial: "Partly done",
  skipped: "Skipped",
  rescheduled: "Moved",
};

export function SessionItem({
  session,
  color,
  actions = true,
}: {
  session: Session;
  color: string;
  actions?: boolean;
}) {
  const tz = useTimezone();
  const now = useNow();
  const update = useUpdateSession();
  const reschedule = useRescheduleSession();
  const [partial, setPartial] = useState(false);
  const [minutes, setMinutes] = useState(Math.round(session.minutes / 2));
  const ended = new Date(session.end).getTime() < now;
  const live = !ended && new Date(session.start).getTime() <= now;
  const planned = session.status === "planned";

  const mark = (status: "done" | "skipped" | "partial", completed?: number) =>
    update.mutate(
      { id: session.id, status, completed_minutes: completed },
      {
        onSuccess: () => {
          setPartial(false);
          if (status !== "done") return;
          toast.info("Marked done.", {
            label: "Undo",
            run: () => update.mutate({ id: session.id, status: "planned" }),
          });
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );

  return (
    <article
      className={cx(
        "flex flex-col gap-2 border-l-4 bg-surface px-4 py-3",
        !planned && "opacity-70",
        live && "ring-2 ring-pine ring-offset-2 ring-offset-paper",
      )}
      style={{ borderLeftColor: color }}
      aria-label={`${session.task_title}, ${formatTime(session.start, tz)} to ${formatTime(session.end, tz)}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="text-sm font-bold tabular-nums text-ink-soft">
          {formatTime(session.start, tz)}–{formatTime(session.end, tz)} · {session.minutes} min
          {live && <span className="ml-2 text-pine-strong">Now</span>}
        </p>
        <p className="text-xs font-bold text-ink-soft">
          {kindLabel[session.kind] ?? session.kind}
          {session.at_risk && <span className="ml-2 text-berry">Tight deadline</span>}
          {!planned && (
            <span className="ml-2">{statusLabel[session.status] ?? session.status}</span>
          )}
        </p>
      </div>
      <Link
        to={sessionLink(session, session.course)}
        className={cx("font-bold hover:underline", session.status === "skipped" && "line-through")}
      >
        {session.task_title.replace(/^[A-Z]+ \d+ · /, "")}
      </Link>
      {actions && planned && (
        <div className="flex flex-wrap gap-1">
          {partial ? (
            <form
              className="flex flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                mark("partial", minutes);
              }}
            >
              <label className="flex flex-col text-xs font-bold">
                Minutes done
                <input
                  type="number"
                  min={1}
                  max={session.minutes - 1}
                  value={minutes}
                  onChange={(e) => setMinutes(Number(e.target.value))}
                  className="min-h-11 w-24 rounded-md border border-line bg-surface px-2 text-base font-normal"
                />
              </label>
              <Button
                type="submit"
                size="sm"
                pending={update.isPending}
                disabled={minutes < 1 || minutes >= session.minutes}
              >
                Save
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setPartial(false)}>
                Cancel
              </Button>
            </form>
          ) : (
            <>
              <Button
                size="sm"
                pending={update.isPending && update.variables?.status === "done"}
                onClick={() => mark("done")}
              >
                Done
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setPartial(true)}>
                Partly done
              </Button>
              <Button
                size="sm"
                variant="ghost"
                pending={update.isPending && update.variables?.status === "skipped"}
                onClick={() => mark("skipped")}
              >
                Skip
              </Button>
              {!ended && (
                <Button
                  size="sm"
                  variant="ghost"
                  pending={reschedule.isPending}
                  onClick={() =>
                    reschedule.mutate(session.id, {
                      onSuccess: () => toast.success("Moved. Pulse found another slot."),
                      onError: (err) => toast.error(errorMessage(err)),
                    })
                  }
                >
                  Reschedule
                </Button>
              )}
            </>
          )}
        </div>
      )}
    </article>
  );
}

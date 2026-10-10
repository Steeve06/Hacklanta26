import { useEffect, useRef, useState } from "react";
import { Confetti } from "@/components/Confetti";
import { Mascot } from "@/components/mascot/Mascot";
import type { MascotMood } from "@/components/mascot/types";
import { Skeleton } from "@/components/ui";
import { useMe } from "@/features/auth/hooks";
import { cx } from "@/lib/cx";
import { mascotLine } from "./mascotLines";
import { stateLabel, usePulseStatus } from "./status";

const badge: Record<string, string> = {
  good: "border-pine bg-pine-soft text-pine-strong",
  medium: "border-mustard bg-mustard-soft text-mustard-ink",
  bad: "border-berry bg-berry-soft text-berry",
};

export function StatusPanel() {
  const status = usePulseStatus();
  const me = useMe();
  const previous = useRef<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const data = status.data;
  const state = (data?.overall.state ?? "good") as MascotMood;

  useEffect(() => {
    if (!data) return;
    const current = data.overall.state;
    if (previous.current && previous.current !== current) {
      const count = data.overall.reasons.length;
      setAnnouncement(
        `Status changed to ${stateLabel[current]}${count ? `: ${count} item${count > 1 ? "s" : ""} need attention` : ""}.`,
      );
    }
    previous.current = current;
  }, [data]);

  if (status.isPending) return <Skeleton className="h-40 w-full" />;
  if (!data) return null;

  const sass = me.data?.profile?.supportive_mode ? 1 : (me.data?.profile?.sass_level ?? 3);
  const moment = data.moment;
  return (
    <section
      aria-labelledby="status-heading"
      className="relative flex flex-col gap-4 rounded-lg border border-line bg-surface p-4 sm:flex-row sm:items-center sm:p-5"
    >
      <div className="relative mx-auto shrink-0 sm:mx-0">
        <Mascot
          mood={state}
          moment={moment ? { kind: moment.kind, key: moment.key } : null}
          size={140}
        />
        <Confetti show={moment?.kind === "celebrate"} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="status-heading" className="sr-only">
            How you're doing
          </h2>
          <span className={cx("rounded-full border px-3 py-0.5 text-sm font-bold", badge[state])}>
            {stateLabel[state]}
          </span>
          <span className="text-sm text-ink-soft">Score {data.overall.score} of 100</span>
        </div>
        <p className="font-display text-xl font-bold leading-snug">
          {mascotLine(state, { fresh: data.fresh_start, allDone: data.all_done, sass })}
        </p>
        {data.overall.reasons.length > 0 && (
          <ul className="flex flex-col gap-1 text-sm">
            {data.overall.reasons.map((reason) => (
              <li key={reason} className="flex gap-2">
                <span
                  aria-hidden="true"
                  className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-ink-soft"
                />
                {reason}
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </section>
  );
}

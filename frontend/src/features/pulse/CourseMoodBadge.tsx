import { MascotStill } from "@/components/mascot/MascotStill";
import type { MascotMood } from "@/components/mascot/types";
import { ProgressRing } from "@/components/ProgressRing";
import { stateLabel, usePulseStatus } from "./status";

export function CourseMoodBadge({ courseId }: { courseId: number }) {
  const status = usePulseStatus();
  const entry = status.data?.courses.find((c) => c.course_id === courseId);
  if (!entry) return null;
  return (
    <div className="flex shrink-0 flex-col items-center gap-1">
      <div className="relative">
        <ProgressRing
          value={entry.score}
          state={entry.state}
          label={`${entry.code}: ${stateLabel[entry.state]}, score ${entry.score}`}
        />
        <MascotStill
          mood={entry.state as MascotMood}
          size={30}
          className="absolute -bottom-2 -right-3"
        />
      </div>
      <span className="text-xs font-bold text-ink-soft">{stateLabel[entry.state]}</span>
    </div>
  );
}

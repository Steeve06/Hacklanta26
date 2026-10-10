import { useEffect } from "react";
import { syncPush } from "@/features/notifications/push";
import { usePulseStatus } from "@/features/pulse/status";

export function ShellExtras() {
  const status = usePulseStatus();
  const mood = status.data?.overall.state;
  useEffect(() => {
    syncPush().catch(() => {
      // Push is a bonus channel; the inbox and email still carry every reminder.
    });
  }, []);
  useEffect(() => {
    if (mood) document.body.dataset.mood = mood;
    return () => {
      delete document.body.dataset.mood;
    };
  }, [mood]);
  return null;
}

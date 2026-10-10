import { useEffect } from "react";
import { usePulseStatus } from "@/features/pulse/status";

export function ShellExtras() {
  const status = usePulseStatus();
  const mood = status.data?.overall.state;
  useEffect(() => {
    if (mood) document.body.dataset.mood = mood;
    return () => {
      delete document.body.dataset.mood;
    };
  }, [mood]);
  return null;
}

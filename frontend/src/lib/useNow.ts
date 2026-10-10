import { useEffect, useState } from "react";
import { serverNow, useServerClock } from "./serverClock";

export function useNow(intervalMs = 30_000): number {
  const offset = useServerClock((s) => s.offsetMs);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now + offset;
}

export { serverNow };

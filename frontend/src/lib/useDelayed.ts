import { useEffect, useState } from "react";

export const LOADING_DELAY_MS = 300;

export function useDelayed(active: boolean, delay = LOADING_DELAY_MS): boolean {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!active) return;
    const timer = window.setTimeout(() => setVisible(true), delay);
    return () => {
      window.clearTimeout(timer);
      setVisible(false);
    };
  }, [active, delay]);
  return active && visible;
}

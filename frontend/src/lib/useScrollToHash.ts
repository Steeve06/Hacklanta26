import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/** Scroll to the element named by the URL hash once the page has rendered it. Client-side
 * navigation doesn't do this on its own. */
export function useScrollToHash(ready: boolean): void {
  const { hash } = useLocation();
  useEffect(() => {
    if (!ready || !hash) return;
    document.getElementById(hash.slice(1))?.scrollIntoView?.({ block: "start" });
  }, [ready, hash]);
}

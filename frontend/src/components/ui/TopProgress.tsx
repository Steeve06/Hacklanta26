import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useNavigation } from "react-router-dom";
import { useDelayed } from "@/lib/useDelayed";

export function TopProgress({ active: forced = false }: { active?: boolean }) {
  const fetching = useIsFetching();
  const mutating = useIsMutating();
  const navigation = useNavigation();
  const active = useDelayed(forced || fetching > 0 || mutating > 0 || navigation.state !== "idle");
  if (!active) return null;
  return (
    <div
      className="fixed inset-x-0 top-0 z-50 h-[3px] overflow-hidden bg-pine-soft"
      role="progressbar"
      aria-label="Loading"
    >
      <div className="h-full w-1/3 animate-progress-indeterminate bg-pine" />
    </div>
  );
}

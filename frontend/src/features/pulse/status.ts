import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { useMe } from "@/features/auth/hooks";

export type Status = components["schemas"]["Status"];
export type StatusEntry = components["schemas"]["StatusEntry"];

export const statusKey = ["pulse", "status"] as const;

export function usePulseStatus() {
  const me = useMe();
  return useQuery({
    queryKey: statusKey,
    enabled: me.data?.role === "student" && Boolean(me.data.profile?.onboarding_done),
    queryFn: async () => unwrap(await api.GET("/api/v1/pulse/status")),
    refetchInterval: 60_000,
  });
}

export const stateLabel: Record<string, string> = {
  good: "On track",
  medium: "Needs attention",
  bad: "Falling behind",
};

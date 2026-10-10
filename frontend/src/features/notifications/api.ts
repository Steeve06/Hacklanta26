import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { meKey, useMe } from "@/features/auth/hooks";

export type Notification = components["schemas"]["Notification"];
export const inboxKey = ["notifications"] as const;

export function useInbox() {
  const me = useMe();
  return useQuery({
    queryKey: inboxKey,
    enabled: me.data?.role === "student",
    queryFn: async () => unwrap(await api.GET("/api/v1/notifications")),
    refetchInterval: 60_000,
  });
}

export function useNotificationAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, action }: { id: number; action: "open" | "snooze" | "tone_down" }) =>
      unwrap(
        await api.POST("/api/v1/notifications/{notification_id}/action", {
          params: { path: { notification_id: id } },
          body: { action },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: inboxKey });
      void client.invalidateQueries({ queryKey: meKey });
    },
  });
}

export function useMarkAllRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/notifications/read-all");
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: inboxKey }),
  });
}

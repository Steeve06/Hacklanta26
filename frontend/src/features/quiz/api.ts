import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";

export type Check = components["schemas"]["StudyCheck"];
export type CheckDetail = components["schemas"]["StudyCheckDetail"];
export type CheckCard = components["schemas"]["CheckCard"];
export type Streak = components["schemas"]["Streak"];
export type StreakDay = components["schemas"]["StreakDay"];

export const checkKeys = {
  all: ["checks"] as const,
  list: (state: string) => ["checks", "list", state] as const,
  detail: (id: number) => ["checks", "detail", id] as const,
  streak: ["checks", "streak"] as const,
};

export function useChecks(state: "open" | "upcoming" | "past") {
  return useQuery({
    queryKey: checkKeys.list(state),
    queryFn: async () => unwrap(await api.GET("/api/v1/checks", { params: { query: { state } } })),
    refetchInterval: 60_000,
  });
}

export function useCheck(id: number) {
  return useQuery({
    queryKey: checkKeys.detail(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/checks/{check_id}", { params: { path: { check_id: id } } })),
  });
}

export function useStreak() {
  return useQuery({
    queryKey: checkKeys.streak,
    queryFn: async () => unwrap(await api.GET("/api/v1/streak")),
    refetchInterval: 60_000,
  });
}

function useStoreCheck(id: number) {
  const client = useQueryClient();
  return (check: CheckDetail) => {
    client.setQueryData(checkKeys.detail(id), check);
    if (check.state !== "open") {
      void client.invalidateQueries({ queryKey: checkKeys.all, refetchType: "inactive" });
      void client.invalidateQueries({ queryKey: checkKeys.streak });
      void client.invalidateQueries({ queryKey: ["pulse", "status"] });
      void client.invalidateQueries({ queryKey: ["notifications"] });
    }
  };
}

export function useStartCheck(id: number) {
  const store = useStoreCheck(id);
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/checks/{check_id}/start", { params: { path: { check_id: id } } }),
      ),
    onSuccess: store,
  });
}

export function useAnswerCard(id: number) {
  const store = useStoreCheck(id);
  return useMutation({
    mutationFn: async (body: { position: number; choice: number }) =>
      unwrap(
        await api.POST("/api/v1/checks/{check_id}/answer", {
          params: { path: { check_id: id } },
          body,
        }),
      ),
    onSuccess: store,
  });
}

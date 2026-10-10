import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, refreshAccess, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { useServerClock } from "@/lib/serverClock";
import { useAuth } from "./store";

export type Me = components["schemas"]["Me"];

export const meKey = ["me"] as const;

export function useBootstrapSession() {
  return useQuery({
    queryKey: ["session-bootstrap"],
    queryFn: async () => {
      const token = await refreshAccess();
      if (!token) useAuth.getState().expire();
      return Boolean(token);
    },
    staleTime: Infinity,
    retry: false,
  });
}

export function useMe() {
  const status = useAuth((s) => s.status);
  return useQuery({
    queryKey: meKey,
    queryFn: async () => {
      const me = unwrap(await api.GET("/api/v1/me"));
      useServerClock.getState().sync(me.server_now);
      return me;
    },
    enabled: status === "signed-in",
    staleTime: 60_000,
  });
}

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { email: string; password: string; remember: boolean }) =>
      unwrap(await api.POST("/api/v1/auth/login", { body })),
    onSuccess: (data) => {
      useAuth.getState().setAccess(data.access);
      void client.invalidateQueries({ queryKey: meKey });
    },
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/auth/logout");
    },
    onSettled: () => {
      useAuth.getState().expire();
      client.clear();
    },
  });
}

export function useUpdateMe() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: components["schemas"]["PatchedMeUpdateRequest"]) =>
      unwrap(await api.PATCH("/api/v1/me", { body })),
    onSuccess: (data) => client.setQueryData(meKey, data),
  });
}

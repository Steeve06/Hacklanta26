import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, refreshAccess, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { useServerClock } from "@/lib/serverClock";
import { useAuth } from "./store";

export type Me = components["schemas"]["Me"];
type Signup = components["schemas"]["SignupRequest"];

export const meKey = ["me"] as const;
export const bootstrapKey = ["session-bootstrap"] as const;

/** Restore the session from the refresh cookie once per page load. */
export function useBootstrapSession() {
  return useQuery({
    queryKey: bootstrapKey,
    queryFn: async () => {
      const result = await refreshAccess();
      if (result === "expired") useAuth.getState().expire();
      return result;
    },
    staleTime: Infinity,
    retry: false,
  });
}

async function fetchMe(): Promise<Me> {
  const me = unwrap(await api.GET("/api/v1/me"));
  useServerClock.getState().sync(me.server_now);
  return me;
}

export function useMe() {
  const status = useAuth((s) => s.status);
  return useQuery({
    queryKey: meKey,
    queryFn: fetchMe,
    enabled: status === "signed-in",
    staleTime: 60_000,
  });
}

/** Sign in, then load the profile so the caller can send the user to the right page. */
export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { email: string; password: string; remember: boolean }) => {
      const { access } = unwrap(await api.POST("/api/v1/auth/login", { body }));
      useAuth.getState().setAccess(access);
      return fetchMe();
    },
    onSuccess: (me) => {
      client.setQueryData(meKey, me);
      client.setQueryData(bootstrapKey, "ok");
    },
  });
}

export function useSignup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: Signup) => {
      const { access } = unwrap(await api.POST("/api/v1/auth/signup", { body }));
      useAuth.getState().setAccess(access);
      return fetchMe();
    },
    onSuccess: (me) => {
      client.setQueryData(meKey, me);
      client.setQueryData(bootstrapKey, "ok");
    },
  });
}

export function useRequestReset() {
  return useMutation({
    mutationFn: async (email: string) =>
      unwrap(await api.POST("/api/v1/auth/password/reset", { body: { email } })),
  });
}

export function useConfirmReset() {
  return useMutation({
    mutationFn: async (body: components["schemas"]["PasswordResetConfirmRequest"]) =>
      unwrap(await api.POST("/api/v1/auth/password/reset/confirm", { body })),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (body: components["schemas"]["PasswordChangeRequest"]) =>
      unwrap(await api.POST("/api/v1/auth/password/change", { body })),
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
      client.setQueryData(bootstrapKey, "expired");
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

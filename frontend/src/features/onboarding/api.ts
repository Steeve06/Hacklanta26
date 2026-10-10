import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { toast } from "@/components/ui";
import { meKey } from "@/features/auth/hooks";

export type OnboardingState = components["schemas"]["OnboardingState"];
export const onboardingKey = ["onboarding"] as const;

export function useOnboarding() {
  return useQuery({
    queryKey: onboardingKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/onboarding")),
    staleTime: 0,
  });
}

/** Save a step (with `data`) or just move to it (without). The server answers with the full
 * state; when another tab saved in between, it says so and this tab shows the latest. */
export function useSaveStep() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { step: number; data?: Record<string, unknown> }) => {
      const version = client.getQueryData<OnboardingState>(onboardingKey)?.version;
      return unwrap(await api.PATCH("/api/v1/onboarding", { body: { ...body, version } }));
    },
    onSuccess: (state) => {
      client.setQueryData(onboardingKey, state);
      if (state.stale) toast.info("Your onboarding changed in another tab. Showing the latest.");
      if (state.note) toast.info(state.note);
    },
  });
}

export function useCompleteOnboarding() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/onboarding/complete")),
    onSuccess: (me) => {
      client.setQueryData(meKey, me);
      void client.invalidateQueries({ queryKey: onboardingKey });
    },
  });
}

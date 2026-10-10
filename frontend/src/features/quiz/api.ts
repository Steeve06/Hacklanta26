import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";

export type Quiz = components["schemas"]["ChapterQuiz"];
export type QuizDetail = components["schemas"]["ChapterQuizDetail"];
export type Streak = components["schemas"]["Streak"];

export const quizKeys = {
  list: (state: string) => ["quizzes", state] as const,
  detail: (id: number) => ["quizzes", "detail", id] as const,
  streak: ["quizzes", "streak"] as const,
};

export function useQuizzes(state: "open" | "upcoming" | "closed") {
  return useQuery({
    queryKey: quizKeys.list(state),
    queryFn: async () => unwrap(await api.GET("/api/v1/quizzes", { params: { query: { state } } })),
    refetchInterval: 60_000,
  });
}

export function useQuiz(id: number) {
  return useQuery({
    queryKey: quizKeys.detail(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/quizzes/{quiz_id}", { params: { path: { quiz_id: id } } })),
  });
}

export function useStreak() {
  return useQuery({
    queryKey: quizKeys.streak,
    queryFn: async () => unwrap(await api.GET("/api/v1/streak")),
  });
}

export function useStartQuiz(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/quizzes/{quiz_id}/start", { params: { path: { quiz_id: id } } }),
      ),
    onSuccess: (quiz) => client.setQueryData(quizKeys.detail(id), quiz),
  });
}

export function useSubmitQuiz(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (answers: Record<string, number>) =>
      unwrap(
        await api.POST("/api/v1/quizzes/{quiz_id}/submit", {
          params: { path: { quiz_id: id } },
          body: { answers },
        }),
      ),
    onSuccess: (quiz) => {
      client.setQueryData(quizKeys.detail(id), quiz);
      for (const state of ["open", "upcoming", "closed"])
        void client.invalidateQueries({ queryKey: quizKeys.list(state) });
      void client.invalidateQueries({ queryKey: quizKeys.streak });
      void client.invalidateQueries({ queryKey: ["pulse", "status"] });
      void client.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

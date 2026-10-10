import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";

export type Deck = components["schemas"]["DailyDeck"];
export type DeckDetail = components["schemas"]["DailyDeckDetail"];
export type DeckItem = components["schemas"]["DeckItem"];
export type Leaderboard = components["schemas"]["Leaderboard"];
export type LeaderboardRow = components["schemas"]["LeaderboardRow"];
export type Streak = components["schemas"]["Streak"];
export type StreakDay = components["schemas"]["StreakDay"];

/** What a student sends for one question. */
export type ItemResponse =
  { knew: boolean } | { choice: number } | { text: string } | { pairs: number[] };

/** Shown after answering: the right answer for single questions, or the right pairing. */
export type Solution = { answer?: string; explanation?: string; choice?: number; pairs?: number[] };

export const deckKeys = {
  list: ["decks"] as const,
  today: ["decks", "today"] as const,
  detail: (id: number) => ["decks", "detail", id] as const,
  streak: ["decks", "streak"] as const,
  leaderboard: (courseId: number | null) => ["decks", "leaderboard", courseId] as const,
};

export function useDecks() {
  return useQuery({
    queryKey: deckKeys.list,
    queryFn: async () => unwrap(await api.GET("/api/v1/decks")),
  });
}

export function useTodayDeck() {
  return useQuery({
    queryKey: deckKeys.today,
    queryFn: async () => unwrap(await api.GET("/api/v1/decks/today")),
  });
}

export function useDeck(id: number) {
  return useQuery({
    queryKey: deckKeys.detail(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/decks/{deck_id}", { params: { path: { deck_id: id } } })),
  });
}

export function useStreak() {
  return useQuery({
    queryKey: deckKeys.streak,
    queryFn: async () => unwrap(await api.GET("/api/v1/streak")),
    refetchInterval: 60_000,
  });
}

export function useLeaderboard(courseId: number | null) {
  return useQuery({
    queryKey: deckKeys.leaderboard(courseId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/leaderboard", {
          params: { query: courseId ? { course_id: courseId } : {} },
        }),
      ),
    placeholderData: (previous) => previous,
  });
}

/** Put a fresh copy of a session everywhere it's cached; refresh the rest once it's finished. */
function store(client: QueryClient, deck: DeckDetail) {
  client.setQueryData(deckKeys.detail(deck.id), deck);
  const today = client.getQueryData<DeckDetail>(deckKeys.today);
  if (today?.id === deck.id) client.setQueryData(deckKeys.today, deck);
  if (deck.completed_at) {
    void client.invalidateQueries({ queryKey: deckKeys.list, exact: true });
    void client.invalidateQueries({ queryKey: deckKeys.streak });
    void client.invalidateQueries({ queryKey: ["decks", "leaderboard"] });
    void client.invalidateQueries({ queryKey: ["pulse", "status"] });
    void client.invalidateQueries({ queryKey: ["notifications"] });
  }
}

export function useStartDeck(deckId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/decks/{deck_id}/start", { params: { path: { deck_id: deckId } } }),
      ),
    onSuccess: (deck) => store(client, deck),
  });
}

export function useAnswer(deckId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { position: number; response: ItemResponse }) =>
      unwrap(
        await api.POST("/api/v1/decks/{deck_id}/answer", {
          params: { path: { deck_id: deckId } },
          body,
        }),
      ),
    onSuccess: (deck) => store(client, deck),
  });
}

/** Ask the server for the session again, e.g. when the clock runs out (it finishes it then). */
export function useRefreshDeck(deckId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.GET("/api/v1/decks/{deck_id}", { params: { path: { deck_id: deckId } } })),
    onSuccess: (deck) => store(client, deck),
  });
}

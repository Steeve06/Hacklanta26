import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";

export type Deck = components["schemas"]["DailyDeck"];
export type DeckDetail = components["schemas"]["DailyDeckDetail"];
export type DeckCard = components["schemas"]["DeckCard"];
export type Streak = components["schemas"]["Streak"];
export type StreakDay = components["schemas"]["StreakDay"];

export const deckKeys = {
  list: ["decks"] as const,
  today: ["decks", "today"] as const,
  detail: (id: number) => ["decks", "detail", id] as const,
  streak: ["decks", "streak"] as const,
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

export function useReviewCard(deckId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { card_id: number; knew: boolean }) =>
      unwrap(
        await api.POST("/api/v1/decks/{deck_id}/review", {
          params: { path: { deck_id: deckId } },
          body,
        }),
      ),
    onSuccess: (deck) => {
      client.setQueryData(deckKeys.detail(deckId), deck);
      const today = client.getQueryData<DeckDetail>(deckKeys.today);
      if (today?.id === deckId) client.setQueryData(deckKeys.today, deck);
      if (deck.completed_at) {
        void client.invalidateQueries({ queryKey: deckKeys.list });
        void client.invalidateQueries({ queryKey: deckKeys.streak });
        void client.invalidateQueries({ queryKey: ["pulse", "status"] });
        void client.invalidateQueries({ queryKey: ["notifications"] });
      }
    },
  });
}

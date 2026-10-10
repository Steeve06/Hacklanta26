import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { meKey } from "@/features/auth/hooks";
import { checkKeys } from "@/features/quiz/api";

export type Conversation = components["schemas"]["Conversation"];
export type ChatMessage = components["schemas"]["ChatMessage"];

export const conversationKey = ["assistant", "conversation"] as const;
const POLL_MS = 1500;

export function isWaiting(conversation: Conversation | undefined): boolean {
  return Boolean(conversation?.messages.some((m) => m.state === "pending"));
}

export function useConversation(enabled: boolean) {
  return useQuery({
    queryKey: conversationKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/assistant/conversation")),
    enabled,
    refetchInterval: (query) => (isWaiting(query.state.data) ? POLL_MS : false),
  });
}

export function useSendMessage() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) =>
      unwrap(await api.POST("/api/v1/assistant/messages", { body: { text } })),
    onSuccess: (conversation) => client.setQueryData(conversationKey, conversation),
  });
}

function useAnswer(path: "confirm" | "decline") {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.POST(`/api/v1/assistant/messages/{message_id}/${path}`, {
          params: { path: { message_id: id } },
        }),
      ),
    onSuccess: (message) => {
      client.setQueryData<Conversation>(conversationKey, (old) =>
        old
          ? { ...old, messages: old.messages.map((m) => (m.id === message.id ? message : m)) }
          : old,
      );
      if (message.proposal === "applied") {
        void client.invalidateQueries({ queryKey: ["pulse"] });
        void client.invalidateQueries({ queryKey: checkKeys.all });
        void client.invalidateQueries({ queryKey: meKey });
      }
    },
  });
}

export const useConfirmChanges = () => useAnswer("confirm");
export const useDeclineChanges = () => useAnswer("decline");

export function useStartOver() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.DELETE("/api/v1/assistant/conversation")),
    onSuccess: () =>
      client.setQueryData<Conversation>(conversationKey, {
        id: null,
        created_at: null,
        messages: [],
      }),
  });
}

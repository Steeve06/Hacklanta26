import { create } from "zustand";

export type Toast = {
  id: number;
  message: string;
  tone: "info" | "error" | "success";
  action?: { label: string; run: () => void };
};

type ToastState = {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id">, ttl?: number) => void;
  dismiss: (id: number) => void;
};

let nextId = 1;

export const useToasts = create<ToastState>((set, get) => ({
  toasts: [],
  push: (toast, ttl = 5000) => {
    const id = nextId++;
    set({ toasts: [...get().toasts.slice(-2), { ...toast, id }] });
    window.setTimeout(() => get().dismiss(id), ttl);
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}));

export const toast = {
  info: (message: string, action?: Toast["action"]) =>
    useToasts.getState().push({ message, tone: "info", action }, action ? 8000 : 5000),
  success: (message: string) => useToasts.getState().push({ message, tone: "success" }),
  error: (message: string) => useToasts.getState().push({ message, tone: "error" }, 7000),
};

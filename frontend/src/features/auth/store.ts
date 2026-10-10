import { create } from "zustand";

type AuthState = {
  access: string | null;
  status: "unknown" | "signed-in" | "signed-out";
  setAccess: (token: string) => void;
  expire: () => void;
};

export const useAuth = create<AuthState>((set) => ({
  access: null,
  status: "unknown",
  setAccess: (token) => set({ access: token, status: "signed-in" }),
  expire: () => set({ access: null, status: "signed-out" }),
}));

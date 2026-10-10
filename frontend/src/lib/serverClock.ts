import { create } from "zustand";

/** Difference between the server's clock for this user and the device clock, in ms. The server is
 * authoritative; in demo mode its clock can also be shifted (time-travel). */
export const useServerClock = create<{ offsetMs: number; sync: (serverIso: string) => void }>(
  (set) => ({
    offsetMs: 0,
    sync: (serverIso) => set({ offsetMs: Date.parse(serverIso) - Date.now() }),
  }),
);

export function serverNow(): number {
  return Date.now() + useServerClock.getState().offsetMs;
}

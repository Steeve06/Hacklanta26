import { create } from "zustand";

/** The browser's install offer (Chrome, Edge, Android). Safari has none; iPhone users add Leon
 * from the Share menu instead. */
type InstallPrompt = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

type InstallState = {
  prompt: InstallPrompt | null;
  installed: boolean;
};

export const useInstall = create<InstallState>(() => ({
  prompt: null,
  installed: isStandalone(),
}));

export function isStandalone(): boolean {
  const nav = navigator as Navigator & { standalone?: boolean };
  return Boolean(window.matchMedia?.("(display-mode: standalone)").matches || nav.standalone);
}

export function isIos(): boolean {
  const ua = navigator.userAgent;
  return /iPhone|iPad|iPod/.test(ua) || (ua.includes("Macintosh") && navigator.maxTouchPoints > 1);
}

export async function install(): Promise<boolean> {
  const prompt = useInstall.getState().prompt;
  if (!prompt) return false;
  await prompt.prompt();
  const { outcome } = await prompt.userChoice;
  useInstall.setState({ prompt: null, installed: outcome === "accepted" });
  return outcome === "accepted";
}

/** Register the service worker (push and the offline app shell) and listen for the install
 * offer, which can arrive before React has rendered anything. */
export function startPwa(): void {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    useInstall.setState({ prompt: event as InstallPrompt });
  });
  window.addEventListener("appinstalled", () => {
    useInstall.setState({ prompt: null, installed: true });
  });
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
        // No service worker (private browsing, insecure origin): Leon still works in the tab.
      });
    });
  }
}

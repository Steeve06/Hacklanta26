import { api, unwrap } from "@/api/client";

export type PushState = "unsupported" | "off" | "on" | "blocked" | "unavailable";

function supported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function keyBytes(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

/** Subscribe this device (or reuse its subscription) and store it on the server. */
async function subscribeAndSave(registration: ServiceWorkerRegistration, publicKey: string) {
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes(publicKey),
    }));
  const json = subscription.toJSON();
  unwrap(
    await api.POST("/api/v1/push/subscribe", {
      body: {
        endpoint: json.endpoint ?? "",
        keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
      },
    }),
  );
}

export async function pushState(): Promise<PushState> {
  if (!supported()) return "unsupported";
  if (Notification.permission === "denied") return "blocked";
  const config = unwrap(await api.GET("/api/v1/push/subscribe"));
  if (!config.enabled) return "unavailable";
  const registration = await navigator.serviceWorker.getRegistration("/");
  const subscription = await registration?.pushManager.getSubscription();
  return subscription ? "on" : "off";
}

export async function enablePush(): Promise<PushState> {
  if (!supported()) return "unsupported";
  const config = unwrap(await api.GET("/api/v1/push/subscribe"));
  if (!config.enabled) return "unavailable";
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission === "denied" ? "blocked" : "off";
  const registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  await navigator.serviceWorker.ready;
  await subscribeAndSave(registration, config.public_key);
  return "on";
}

/** If this device already allowed notifications, make sure the server has its subscription
 * (after a reinstall, a new browser profile or a reset database). Never asks for permission. */
export async function syncPush(): Promise<void> {
  if (!supported() || Notification.permission !== "granted") return;
  const config = unwrap(await api.GET("/api/v1/push/subscribe"));
  if (!config.enabled) return;
  const registration = await navigator.serviceWorker.ready;
  await subscribeAndSave(registration, config.public_key);
}

export async function sendTestPush(): Promise<number> {
  return unwrap(await api.POST("/api/v1/push/test")).sent;
}

export async function disablePush(): Promise<PushState> {
  const registration = await navigator.serviceWorker.getRegistration("/");
  const subscription = await registration?.pushManager.getSubscription();
  if (subscription) {
    await api.DELETE("/api/v1/push/subscribe", {
      params: { query: { endpoint: subscription.endpoint } },
    });
    await subscription.unsubscribe();
  }
  return "off";
}

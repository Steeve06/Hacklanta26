// Leon's service worker: reminders as push notifications, and an app shell that still opens
// without a connection. The API is never cached, so nothing a student sees can be stale data.
const VERSION = "leon-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/badge-96.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function skipped(url) {
  // API calls, Django admin and the dev server's own files always go to the network.
  return /^\/(api|admin|static|@vite|@react-refresh|src|node_modules)\b/.test(url.pathname);
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || skipped(url)) return;

  if (request.mode === "navigate") {
    // Pages: the network first, so a deploy shows up at once; the saved shell when offline.
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put("/", copy));
          return response;
        })
        .catch(() => caches.match("/")),
    );
    return;
  }

  if (/^\/(assets|icons)\//.test(url.pathname)) {
    // Built files have a content hash in their name, so a saved copy is always right.
    event.respondWith(
      caches.match(request).then(
        (saved) =>
          saved ||
          fetch(request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(VERSION).then((cache) => cache.put(request, copy));
            }
            return response;
          }),
      ),
    );
  }
});

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { title: "Leon", body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Leon", {
      body: data.body || "",
      icon: "/icons/icon-192.png",
      badge: "/icons/badge-96.png",
      tag: data.id ? `leon-${data.id}` : undefined,
      requireInteraction: Boolean(data.urgent),
      data: { url: data.url || "/pulse/inbox", id: data.id },
      actions: data.actions || [],
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const { url, id } = event.notification.data || {};
  const action = event.action || "open";
  const target = !id
    ? url || "/pulse/today"
    : action === "open"
      ? `${url || "/pulse"}${url && url.includes("?") ? "&" : "?"}notification=${id}`
      : `/pulse/inbox?notification=${id}&action=${action}`;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(async (clients) => {
      for (const client of clients) {
        if (new URL(client.url).origin !== self.location.origin) continue;
        try {
          await client.navigate(target);
          return client.focus();
        } catch {
          // A tab this worker doesn't control can't be navigated; open a new window instead.
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});

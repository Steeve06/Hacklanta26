import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// Headless Chromium can't reach a real push service, so DevTools hands the service worker the
// push message instead. The payload is the one the server sends (backend/tests/test_push_delivery
// checks the server side: VAPID signature, encryption, and this exact JSON). The headless shell CI
// uses has no notification centre, so the test records what the worker asks the device to show.
const ORIGIN = "http://localhost:5174";

test("a push message becomes a notification on the device", async ({ page, context }) => {
  await context.grantPermissions(["notifications"], { origin: ORIGIN });
  const cdp = await context.newCDPSession(page);
  const registrations = new Map<string, string>();
  cdp.on("ServiceWorker.workerRegistrationUpdated", (event) => {
    for (const r of event.registrations) registrations.set(r.scopeURL, r.registrationId);
  });
  await cdp.send("ServiceWorker.enable");

  await signIn(page, "maya@pulse.test");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await expect.poll(() => registrations.get(`${ORIGIN}/`)).toBeTruthy();
  const registrationId = registrations.get(`${ORIGIN}/`) ?? "";

  const worker =
    context.serviceWorkers().find((w) => w.url() === `${ORIGIN}/sw.js`) ??
    (await context.waitForEvent("serviceworker"));
  await worker.evaluate(() => {
    const scope = self as unknown as {
      shown: unknown[];
      registration: ServiceWorkerRegistration;
    };
    scope.shown = [];
    const show = scope.registration.showNotification.bind(scope.registration);
    scope.registration.showNotification = (title: string, options: NotificationOptions = {}) => {
      scope.shown.push({ title, body: options.body, tag: options.tag, data: options.data });
      return show(title, options).catch(() => undefined);
    };
  });

  const payload = {
    id: 4242,
    title: "Leon · New in your course",
    body: "New quiz in CS 201: Quiz 4: Graphs",
    url: "/lms/courses/1/assignments/99",
    urgent: false,
    actions: [{ action: "open", title: "Open" }],
  };
  await cdp.send("ServiceWorker.deliverPushMessage", {
    origin: ORIGIN,
    registrationId,
    data: JSON.stringify(payload),
  });

  const shown = () => worker.evaluate(() => (self as unknown as { shown: unknown[] }).shown);
  await expect.poll(shown).toEqual([
    {
      title: payload.title,
      body: payload.body,
      tag: "leon-4242",
      data: { url: payload.url, id: payload.id },
    },
  ]);
});

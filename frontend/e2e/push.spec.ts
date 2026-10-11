import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// Headless Chromium can't reach a real push service, so DevTools hands the service worker the
// push message instead. The payload is the one the server sends (backend/tests/test_push_delivery
// checks the server side: VAPID signature, encryption, and this exact JSON).
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

  const shown = () =>
    page.evaluate(async () => {
      const registration = await navigator.serviceWorker.ready;
      return (await registration.getNotifications()).map((n) => ({
        title: n.title,
        body: n.body,
        tag: n.tag,
        data: n.data as unknown,
      }));
    });
  await expect.poll(shown).toEqual([
    {
      title: payload.title,
      body: payload.body,
      tag: "leon-4242",
      data: { url: payload.url, id: payload.id },
    },
  ]);
});

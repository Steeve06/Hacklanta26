import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

type Manifest = { name: string; start_url: string; display: string; icons: { src: string }[] };

test("Leon is installable: manifest, icons and a service worker", async ({ page, request }) => {
  const manifest = (await (await request.get("/manifest.webmanifest")).json()) as Manifest;
  expect(manifest.name).toBe("Leon");
  expect(manifest.display).toBe("standalone");
  for (const icon of manifest.icons) {
    const response = await request.get(icon.src);
    expect(response.ok(), icon.src).toBeTruthy();
    expect(response.headers()["content-type"]).toContain("image/png");
  }

  await signIn(page, "maya@pulse.test");
  const scope = await page.evaluate(async () => (await navigator.serviceWorker.ready).scope);
  expect(new URL(scope).pathname).toBe("/");
  await page.reload();
  await expect
    .poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null))
    .toBe(true);
  // Let the reload finish restoring the session first: leaving mid-refresh drops the new cookie.
  await expect(page.getByRole("heading", { name: "Today, Maya" })).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Leon on this device" })).toBeVisible();
});

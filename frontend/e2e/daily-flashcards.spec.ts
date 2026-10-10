import { expect, test } from "@playwright/test";
import { apiAs, signIn } from "./helpers";

type Streak = { current: number; done_today: boolean };

test("finishing today's flashcard deck grows the streak once", async ({ page, request }) => {
  const api = await apiAs(request, "maya@pulse.test");
  const before = await api.get<Streak>("/api/v1/streak");
  if (before.done_today) throw new Error("Maya's deck for today should not be done yet");

  await signIn(page, "maya@pulse.test");
  await page.goto("/pulse/quiz");
  await page.getByRole("link", { name: /Start today's flashcards/ }).click();

  await expect(page.getByRole("progressbar")).toBeVisible();
  for (let i = 0; i < 5; i += 1) {
    await page.getByRole("button", { name: "Show answer" }).click();
    await page.getByRole("button", { name: i % 2 ? "Still learning" : "Got it" }).click();
  }

  await expect(page.getByRole("status")).toContainText(
    `Counted for your streak: ${before.current + 1} days in a row`,
  );

  const after = await api.get<Streak>("/api/v1/streak");
  expect(after.current).toBe(before.current + 1);
  expect(after.done_today).toBe(true);
});

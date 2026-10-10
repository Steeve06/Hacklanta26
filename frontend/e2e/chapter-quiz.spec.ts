import { expect, test } from "@playwright/test";
import { apiAs, signIn } from "./helpers";

type Quiz = { id: number; state: string };
type Streak = { current: number };

test("taking an open chapter quiz in its window grows the streak once", async ({
  page,
  request,
}) => {
  const api = await apiAs(request, "maya@pulse.test");
  const open = await api.get<Quiz[]>("/api/v1/quizzes?state=open");
  const quiz = open[0];
  if (!quiz) throw new Error("Maya should have a quiz open today");
  const before = await api.get<Streak>("/api/v1/streak");

  await signIn(page, "maya@pulse.test");
  await page.goto(`/pulse/quiz/${quiz.id}`);
  await page.getByRole("button", { name: "Start quiz" }).click();
  const questions = page.locator("fieldset");
  await expect(questions.first()).toBeVisible();
  const startedAt = Date.now();
  const count = await questions.count();
  for (let i = 0; i < count; i += 1) {
    await questions.nth(i).getByRole("radio").first().check();
  }
  // The server ignores submissions made less than 20 seconds after starting.
  await page.waitForTimeout(Math.max(0, 21_000 - (Date.now() - startedAt)));
  await page.getByRole("button", { name: "Submit answers" }).click();

  await expect(page.getByRole("status")).toContainText(
    `Counted for your streak: ${before.current + 1} in a row`,
  );
  await expect(page.getByTestId("confetti")).toBeAttached();

  const again = await api.post(`/api/v1/quizzes/${quiz.id}/submit`, { answers: {} });
  expect(again.ok()).toBeTruthy();
  const after = await api.get<Streak>("/api/v1/streak");
  expect(after.current).toBe(before.current + 1);
});

import { expect, test, type Page } from "@playwright/test";
import { apiAs, signIn } from "./helpers";

type Streak = { current: number; done_today: boolean };
type Board = { rows: { xp: number; is_me: boolean }[] };

const myXp = (board: Board) => board.rows.find((r) => r.is_me)?.xp ?? -1;

/** Answer whatever question is on screen; returns false once the results are showing. */
async function answerOne(page: Page): Promise<boolean> {
  const summary = page.getByRole("heading", { name: /correct · \+\d+ XP/ });
  const flip = page.getByRole("button", { name: "Show answer" });
  const typed = page.getByLabel("Your answer");
  const options = page.getByRole("list", { name: "Options" });
  const terms = page.getByRole("list", { name: "Terms" });
  await expect(summary.or(flip).or(typed).or(options).or(terms).first()).toBeVisible();
  if (await summary.isVisible()) return false;
  if (await flip.isVisible()) {
    await flip.click();
    await page.getByRole("button", { name: "Got it" }).click();
    return true;
  }
  if (await typed.isVisible()) {
    await typed.fill("open addressing");
    await page.getByRole("button", { name: "Check" }).click();
  } else if (await options.isVisible()) {
    await options.getByRole("button").first().click();
  } else {
    const sentences = page.getByRole("list", { name: "Sentences" }).getByRole("button");
    for (let i = 0; i < 3; i += 1) {
      await terms.getByRole("button").nth(i).click();
      await sentences.nth(i).click();
    }
    await page.getByRole("button", { name: "Check" }).click();
  }
  await page.getByRole("button", { name: /Continue|See results/ }).click();
  return true;
}

test("today's timed quiz mixes question types, grows the streak and scores XP", async ({
  page,
  request,
}) => {
  const api = await apiAs(request, "maya@pulse.test");
  const before = await api.get<Streak>("/api/v1/streak");
  if (before.done_today) throw new Error("Maya's quiz for today should not be done yet");
  const xpBefore = myXp(await api.get<Board>("/api/v1/leaderboard"));

  await signIn(page, "maya@pulse.test");
  await page.goto("/pulse/quiz");
  const board = page.getByRole("list", { name: "Rankings" });
  await expect(board.getByRole("listitem")).not.toHaveCount(0);
  await expect(board.locator("[aria-current=true]")).toContainText("(you)");

  await page.getByRole("link", { name: /Start today's quiz/ }).click();
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByRole("timer")).toBeVisible();
  for (let i = 0; i < 10 && (await answerOne(page)); i += 1);

  await expect(page.getByRole("status")).toContainText(
    `Counted for your streak: ${before.current + 1} days in a row`,
  );
  const after = await api.get<Streak>("/api/v1/streak");
  expect(after.current).toBe(before.current + 1);
  expect(after.done_today).toBe(true);

  const xpAfter = myXp(await api.get<Board>("/api/v1/leaderboard"));
  expect(xpAfter).toBeGreaterThanOrEqual(xpBefore + 20);
  await page.getByRole("link", { name: "See the leaderboard" }).click();
  await expect(board.locator("[aria-current=true]")).toContainText(`${xpAfter}XP`);
});

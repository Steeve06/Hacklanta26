import { expect, test } from "@playwright/test";
import { apiAs, signIn } from "./helpers";

type Check = { id: number; state: string; card_count: number };
type Streak = { current: number };

test("a study check flips each card and settles the streak once", async ({ page, request }) => {
  const api = await apiAs(request, "maya@pulse.test");
  const open = await api.get<Check[]>("/api/v1/checks?state=open");
  const check = open[0];
  if (!check) throw new Error("Maya should have a study check open today");
  const before = await api.get<Streak>("/api/v1/streak");

  await signIn(page, "maya@pulse.test");
  await page.goto("/pulse/quiz");
  await page
    .getByRole("link", { name: /Study check:/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Start" }).click();

  await expect(page.getByRole("timer")).toBeVisible();
  const kinds: string[] = [];
  for (let i = 0; i < check.card_count; i += 1) {
    const options = page.getByRole("group", { name: "Choose an answer" });
    const typed = page.getByLabel("Your answer");
    const terms = page.getByRole("list", { name: "Terms" });
    await expect(options.or(typed).or(terms).first()).toBeVisible();
    if (await terms.isVisible()) {
      kinds.push("match");
      const termButtons = terms.getByRole("button");
      const clueButtons = page.getByRole("list", { name: "Sentences" }).getByRole("button");
      for (let t = 0; t < 3; t += 1) {
        await termButtons.nth(t).click();
        await clueButtons.nth(t).click();
      }
      await page.getByRole("button", { name: "Check" }).click();
      await expect(page.getByRole("status")).toHaveText(/matched/);
    } else if (await typed.isVisible()) {
      kinds.push("short");
      await typed.fill("retrieval practice");
      await page.getByRole("button", { name: "Check" }).click();
      await expect(page.getByRole("status")).toHaveText(/Right|Not quite/);
    } else {
      kinds.push("choice");
      await options.getByRole("button").first().click();
      await expect(page.getByRole("status")).toHaveText(/Right|Not quite/);
      await expect(page.getByText(/From the chapter/)).toBeVisible();
    }
    const last = i === check.card_count - 1;
    await page.getByRole("button", { name: last ? "See how you did" : "Next card" }).click();
  }
  expect(kinds).toContain("choice");
  await expect(page.getByText(/\d+ XP/).first()).toBeVisible();

  const after = await api.get<Check>(`/api/v1/checks/${check.id}`);
  const streak = await api.get<Streak>("/api/v1/streak");
  if (after.state === "passed") {
    await expect(page.getByRole("status")).toContainText(`${before.current + 1} checks in a row`);
    expect(streak.current).toBe(before.current + 1);
  } else {
    await expect(page.getByRole("button", { name: "Try again with new cards" })).toBeVisible();
    expect(streak.current).toBe(before.current);
  }

  const again = await api.post(`/api/v1/checks/${check.id}/answer`, { position: 0, choice: 1 });
  expect(again.ok()).toBeTruthy();
  expect((await api.get<Streak>("/api/v1/streak")).current).toBe(streak.current);
});

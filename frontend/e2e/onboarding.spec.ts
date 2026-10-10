import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("new student onboards, generates a schedule and lands on Today", async ({ page }) => {
  await signIn(page, "riley@pulse.test");
  await expect(page).toHaveURL(/\/pulse\/onboarding/);
  await expect(page.getByRole("heading", { name: "Let's build your study plan" })).toBeVisible();

  await page.getByRole("button", { name: "These are right" }).click();
  await expect(page.getByRole("heading", { name: "When can you study each week?" })).toBeVisible();
  for (const day of ["Monday", "Tuesday", "Wednesday", "Thursday", "Saturday"]) {
    await page.getByRole("button", { name: `Add time on ${day}` }).click();
    await page.getByRole("button", { name: "Add", exact: true }).click();
  }
  await expect(page.getByText("10 hours a week")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("heading", { name: "How do you like to study?" })).toBeVisible();
  await page.getByRole("button", { name: "Generate my schedule" }).click();

  await expect(page.getByRole("heading", { name: "Here's your schedule" })).toBeVisible({
    timeout: 60_000,
  });
  await page.getByRole("button", { name: "Accept schedule" }).click();

  await expect(page).toHaveURL(/\/pulse$/);
  await expect(page.getByRole("heading", { name: /Today, Riley/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your sessions" })).toBeVisible();
});

import { expect, test, type Page } from "@playwright/test";
import { signIn } from "./helpers";

const PASSWORD = "maple-river-lantern";

async function signUp(page: Page): Promise<string> {
  const email = `e2e-${Date.now()}-${Math.round(Math.random() * 1e6)}@example.edu`;
  await page.goto("/signup");
  await page.getByLabel("First name").fill("Nia");
  await page.getByLabel("Last name").fill("Okoro");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Confirm password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
  return email;
}

const step = (page: Page, n: number) => expect(page.getByText(`Step ${n} of 5`)).toBeVisible();

async function chooseStudyTime(page: Page) {
  for (const cell of [
    "Monday 6 PM to 7 PM",
    "Monday 7 PM to 8 PM",
    "Wednesday 6 PM to 7 PM",
    "Wednesday 7 PM to 8 PM",
    "Saturday 10 AM to 11 AM",
    "Saturday 11 AM to 12 PM",
  ])
    await page.getByRole("button", { name: cell }).click();
  await expect(page.getByText("6 hours a week")).toBeVisible();
}

test("sign up, finish all five onboarding steps and land on Today with a schedule", async ({
  page,
}) => {
  await signUp(page);
  await step(page, 1);
  await page.getByRole("button", { name: "These are right" }).click();

  await step(page, 2);
  await chooseStudyTime(page);
  await page.getByRole("button", { name: "Next" }).click();

  await step(page, 3);
  await page.getByRole("button", { name: "Next" }).click();

  await step(page, 4);
  await page.getByLabel("3. Dramatic").check();
  await expect(page.getByText("You have a plan, right? …Right?")).toBeVisible();
  await page.getByRole("button", { name: "Build my schedule" }).click();

  await step(page, 5);
  await expect(page.getByRole("heading", { name: "The next seven days" })).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByRole("heading", { name: "Your choices" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Daily flashcards" })).toBeVisible();
  await page.getByRole("button", { name: "Looks good" }).click();

  await expect(page).toHaveURL(/\/pulse\/today$/);
  await expect(page.getByRole("heading", { name: /Today, Nia/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your schedule" })).toBeVisible();
});

test("a student halfway through onboarding resumes at the step they left", async ({ page }) => {
  await signIn(page, "casey@pulse.test");
  await expect(page).toHaveURL(/\/onboarding$/);
  await step(page, 3);
  await expect(page.getByRole("heading", { name: "Preferences", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Back" }).click();
  await step(page, 2);
  await expect(page.getByRole("button", { name: "Monday 6 PM to 7 PM" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("an onboarded student goes straight to Today", async ({ page }) => {
  await signIn(page, "sam@pulse.test");
  await expect(page).toHaveURL(/\/pulse\/today$/);
  await page.goto("/onboarding");
  await expect(page).toHaveURL(/\/pulse\/today$/);
});

test("refreshing during step 3 keeps the saved answers", async ({ page }) => {
  await signUp(page);
  await page.getByRole("button", { name: "These are right" }).click();
  await chooseStudyTime(page);
  await page.getByRole("button", { name: "Next" }).click();
  await step(page, 3);
  await page.getByLabel("Most study hours in one day").fill("4");
  await page.getByText("90 minutes").click();
  await page.getByRole("button", { name: "Next" }).click();
  await step(page, 4);
  await page.getByRole("button", { name: "Back" }).click();
  await step(page, 3);

  await page.reload();
  await step(page, 3);
  await expect(page.getByLabel("Most study hours in one day")).toHaveValue("4.0");
  await expect(page.getByRole("radio", { name: "90 minutes" })).toBeChecked();
  await page.getByRole("button", { name: "Back" }).click();
  await step(page, 2);
  await expect(page.getByText("6 hours a week")).toBeVisible();
});

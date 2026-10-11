import { expect, test, type Page } from "@playwright/test";
import { apiAs, PASSWORD, signIn } from "./helpers";

const TEACHER = "kim.lee@school.test";
const CHAPTER = [
  "A **thesis** states the claim an essay argues for in one or two clear sentences.",
  "A **topic sentence** opens each paragraph and tells the reader what it will prove.",
  "**Evidence** such as quotes, data or examples supports each claim in the essay.",
  "A **counterargument** shows you understand the strongest view against your claim.",
  "A **conclusion** returns to the thesis and explains why the argument matters.",
].join(" ");

async function addAssessment(page: Page, action: string, title: string) {
  await page.goto("/teach");
  await page.getByRole("link", { name: action }).click();
  await page.getByLabel("Title").fill(title);
  await page.getByLabel("Instructions (Markdown)").fill(`Instructions for ${title}.`);
}

test("a teacher claims their course, adds content, and a student uses it", async ({
  page,
  request,
  browser,
}) => {
  const admin = await apiAs(request, "admin@pulse.test");
  const registered = await admin.post("/api/v1/teach/registrations", {
    code: "ENG 105",
    title: "Academic Writing",
    teacher_email: TEACHER,
    description: "Writing arguments people believe.",
    meetings: [{ weekday: 1, start_time: "09:00", end_time: "10:15", location: "Hall 2" }],
  });
  expect(registered.status()).toBe(201);
  // No quiet hours for Maya, so announcements arrive whatever time the test runs.
  const maya = await apiAs(request, "maya@pulse.test");
  const quiet = { quiet_start: "12:00", quiet_end: "12:00" };
  expect((await maya.patch("/api/v1/me", { profile: quiet })).ok()).toBeTruthy();

  // The teacher signs up with the registered email and lands on their dashboard.
  await page.goto("/signup");
  await page.getByRole("radio", { name: "I teach a course" }).click();
  await page.getByLabel("First name").fill("Kim");
  await page.getByLabel("Last name").fill("Lee");
  await page.getByLabel("School email").fill(TEACHER);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD + "-teacher");
  await page.getByRole("textbox", { name: "Confirm password" }).fill(PASSWORD + "-teacher");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/teach$/);
  await expect(page.getByRole("heading", { name: "Welcome, Kim" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Academic Writing" })).toBeVisible();
  await expect(page.getByText("Get your course ready")).toBeVisible();

  // A chapter.
  await page.getByRole("link", { name: "Add a chapter" }).click();
  await page.getByLabel("Title").fill("Building an argument");
  await page.getByLabel("Learning objectives").fill("Write a thesis");
  await page.getByLabel("Chapter text (Markdown)").fill(CHAPTER);
  await page.getByRole("button", { name: "Create chapter" }).click();
  await expect(page.getByRole("heading", { name: /Building an argument/ })).toBeVisible();

  // Homework, a discussion and a quiz.
  await addAssessment(page, "Add an assignment", "Essay draft");
  await expect(page.getByRole("heading", { name: "New assignment" })).toBeVisible();
  await page.getByRole("button", { name: "Create assignment" }).click();
  await expect(page).toHaveURL(/assignments\/\d+$/);

  await addAssessment(page, "Start a discussion", "Best argument you heard");
  await expect(page.getByRole("heading", { name: "New discussion" })).toBeVisible();
  await page.getByRole("button", { name: "Create assignment" }).click();
  await expect(page).toHaveURL(/assignments\/\d+$/);

  await addAssessment(page, "Create a quiz", "Quiz 1: Thesis");
  await expect(page.getByRole("heading", { name: "New quiz" })).toBeVisible();
  await page.getByLabel("Question 1").fill("A thesis states the essay's main claim.");
  await page.getByLabel("Kind").selectOption("true_false");
  await page.getByLabel("Correct answer").selectOption({ label: "True" });
  await page.getByRole("button", { name: "Create assignment" }).click();
  await expect(page).toHaveURL(/assignments\/\d+$/);

  await page.goto("/teach");
  const stats = page.locator("dl").first();
  for (const label of ["Chapters", "Assignments", "Discussions", "Quizzes"]) {
    await expect(stats.getByText(label).locator("..")).toContainText("1");
  }
  await expect(page.getByText("Get your course ready")).toHaveCount(0);

  // A student sees all of it, takes the quiz and posts in the discussion.
  const student = await browser.newPage();
  await signIn(student, "maya@pulse.test");
  await student.goto("/lms");
  await student.getByRole("link", { name: /Academic Writing/ }).click();
  await expect(student.getByText("Chapter 1: Building an argument")).toBeVisible();
  await student.getByRole("link", { name: "Assignments" }).click();
  for (const title of ["Essay draft", "Best argument you heard", "Quiz 1: Thesis"])
    await expect(student.getByText(title)).toBeVisible();

  await student.getByText("Quiz 1: Thesis").click();
  await student.getByRole("button", { name: "Start quiz" }).click();
  await student.getByText("True", { exact: true }).click();
  await student.getByRole("button", { name: "Submit answers" }).click();
  await expect(student.getByRole("status")).toContainText("Score: 10");

  await student.goto("/lms");
  await student.getByRole("link", { name: /Academic Writing/ }).click();
  await student.getByRole("link", { name: "Assignments" }).click();
  await student.getByText("Best argument you heard").click();
  await student.getByLabel("Your original post").fill("A teacher once argued for homework.");
  await student.getByRole("button", { name: "Post", exact: true }).click();
  await expect(student.getByText("A teacher once argued for homework.")).toBeVisible();

  // And was told about each new item.
  await student.goto("/pulse/inbox");
  await expect(student.getByText("New quiz in ENG 105: Quiz 1: Thesis")).toBeVisible();
  await expect(student.getByText("New chapter in ENG 105: Building an argument")).toBeVisible();

  const courses = await maya.get<{ code: string; chapters_total: number }[]>("/api/v1/courses");
  expect(courses.find((c) => c.code === "ENG 105")?.chapters_total).toBe(1);
});

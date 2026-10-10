import { expect, test } from "@playwright/test";
import { apiAs, signIn } from "./helpers";

type Session = {
  start: string;
  course: number;
  source_type: string;
  source_id: number;
  kind: string;
  status: string;
};
type Schedule = { sessions: Session[] };
type Assessment = { id: number; type: string; title: string };
type Status = { overall: { score: number } };

test("submitting homework in Learning Hub frees its sessions in Pulse", async ({
  page,
  request,
}) => {
  const api = await apiAs(request, "sam@pulse.test");
  const before = await api.get<Schedule>("/api/v1/pulse/schedule?view=overall");
  const statusBefore = await api.get<Status>("/api/v1/pulse/status");
  const now = Date.now();
  const upcoming = before.sessions.filter(
    (s) => s.source_type === "assessment" && s.status === "planned" && Date.parse(s.start) > now,
  );
  let target: { session: Session; assessment: Assessment } | undefined;
  for (const session of upcoming) {
    const assessment = await api.get<Assessment>(`/api/v1/assessments/${session.source_id}`);
    if (assessment.type === "homework") {
      target = { session, assessment };
      break;
    }
  }
  if (!target) throw new Error("Sam should have upcoming homework sessions");
  const { session, assessment } = target;

  await signIn(page, "sam@pulse.test");
  await page.goto(`/lms/courses/${session.course}/assignments/${assessment.id}`);
  await expect(page.getByRole("heading", { name: assessment.title })).toBeVisible();
  await page.getByLabel("Text answer").fill("My answers are in the attached outline. Q1: a stack.");
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await expect(page.getByText("Submitted.").first()).toBeVisible();

  await page.goto("/pulse");
  await expect(page.getByTestId("confetti")).toBeAttached();

  await expect
    .poll(async () => {
      const after = await api.get<Schedule>("/api/v1/pulse/schedule?view=overall");
      return after.sessions.filter(
        (s) =>
          s.source_type === "assessment" &&
          s.source_id === assessment.id &&
          s.status === "planned" &&
          Date.parse(s.start) > Date.now(),
      ).length;
    })
    .toBe(0);
  const statusAfter = await api.get<Status>("/api/v1/pulse/status");
  expect(statusAfter.overall.score).toBeGreaterThanOrEqual(statusBefore.overall.score);
});

import { expect, test } from "@playwright/test";
import { apiAs, signIn } from "./helpers";

type Session = { start: string; end: string; kind: string; status: string; task_title: string };
type Schedule = { sessions: Session[] };

test("asking Pulse to skip the next session changes nothing until confirmed, then shows it", async ({
  page,
  request,
}) => {
  const api = await apiAs(request, "alex@pulse.test");
  const before = await api.get<Schedule>("/api/v1/pulse/schedule?view=overall");
  const now = Date.now();
  const next = before.sessions
    .filter((s) => s.status === "planned" && s.kind !== "chapter_quiz" && Date.parse(s.end) > now)
    .sort((a, b) => Date.parse(a.start) - Date.parse(b.start))[0];
  expect(next).toBeDefined();

  await signIn(page, "alex@pulse.test");
  await page.getByRole("button", { name: "Ask Pulse" }).first().click();
  const panel = page.getByRole("dialog", { name: "Ask Pulse" });
  await panel.getByLabel("Message").fill("Can you skip my next session?");
  await panel.getByRole("button", { name: "Send" }).click();

  const changes = panel.getByRole("region", { name: "Suggested changes" });
  await expect(changes).toContainText("Skip", { timeout: 15_000 });
  const pending = await api.get<Schedule>("/api/v1/pulse/schedule?view=overall");
  expect(pending.sessions.find((s) => s.start === next?.start)?.status).toBe("planned");

  await changes.getByRole("button", { name: "Confirm" }).click();
  await expect(page).toHaveURL(/\/pulse\/week\?from=\d{4}-\d{2}-\d{2}$/);
  await expect(panel).toBeHidden();
  await expect(page.getByRole("tab", { name: "Study plan", selected: true })).toBeVisible();
  const after = await api.get<Schedule>("/api/v1/pulse/schedule?view=overall");
  expect(after.sessions.find((s) => s.start === next?.start)?.status).toBe("skipped");
});

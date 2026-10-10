import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderRoute } from "@/test/render";
import { MissedDeadlines } from "./MissedDeadlines";

const ago = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();

describe("MissedDeadlines", () => {
  it("says what each miss did to the streak and links to late submission", () => {
    renderRoute(
      <MissedDeadlines
        items={[
          {
            assessment_id: 9,
            course_id: 2,
            course_code: "CS 201",
            title: "Problem Set 2",
            due_at: ago(5),
            late_until: new Date(Date.now() + 86_400_000).toISOString(),
            streak_result: "frozen",
          },
          {
            assessment_id: 10,
            course_id: 3,
            course_code: "PSY 101",
            title: "Quiz 3",
            due_at: ago(30),
            late_until: null,
            streak_result: "missed",
          },
        ]}
      />,
    );
    const [first, second] = screen.getAllByRole("listitem");
    expect(first).toHaveTextContent(/Was due 5 h ago.*· Used a freeze/);
    expect(second).toHaveTextContent(/Reset your streak/);
    const late = screen.getByRole("link", { name: /Submit late until/ });
    expect(late).toHaveAttribute("href", "/lms/courses/2/assignments/9");
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});

import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderRoute } from "@/test/render";
import type { OverloadReport } from "./api";
import { OverloadPanel } from "./OverloadPanel";

const inHours = (h: number) => new Date(Date.now() + h * 3_600_000).toISOString();

function report(items: { title: string; due_at: string }[], unresolvable = false): OverloadReport {
  return {
    items: items.map((i, n) => ({
      source_type: "assessment",
      source_id: n + 1,
      course_code: "PSY 101",
      title: i.title,
      due_at: i.due_at,
      minutes_short: 40,
      needs_longer_block: false,
    })),
    extra_hours_needed: 1,
    at_risk: [],
    suggestions: [{ type: "raise_daily_limit", text: "Raise your most study hours in one day." }],
    unresolvable,
    excluded: [],
  } as OverloadReport;
}

describe("OverloadPanel", () => {
  it("is a closed one-line note, not an alert", async () => {
    renderRoute(<OverloadPanel report={report([{ title: "Essay", due_at: inHours(30) }])} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("1 item won't fully fit before it's due")).toBeVisible();
    expect(screen.getByText("Essay")).not.toBeVisible();
    await userEvent.click(screen.getByText("1 item won't fully fit before it's due"));
    expect(screen.getByText("Essay")).toBeVisible();
    expect(screen.getByText("Raise your most study hours in one day.")).toBeVisible();
  });

  it("only shows work due in the next week when asked to", () => {
    const later = report([{ title: "Final project", due_at: inHours(24 * 20) }]);
    const { container } = renderRoute(<OverloadPanel report={later} soonOnly />);
    expect(container).toBeEmptyDOMElement();
  });

  it("still alerts when there's no study time at all", () => {
    renderRoute(<OverloadPanel report={report([], true)} />);
    expect(screen.getByRole("alert")).toHaveTextContent("You have no study time set");
  });
});

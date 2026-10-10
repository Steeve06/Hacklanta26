import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type { AvailabilityBlock } from "./api";
import { AvailabilityGrid } from "./AvailabilityGrid";
import { fromSlots, mergeBlocks, toSlots, totalHours } from "./availability";

function Harness({ initial = [] }: { initial?: AvailabilityBlock[] }) {
  const [blocks, setBlocks] = useState(initial);
  return (
    <>
      <AvailabilityGrid value={blocks} onChange={setBlocks} />
      <output data-testid="blocks">{JSON.stringify(blocks)}</output>
    </>
  );
}

const blocks = () =>
  JSON.parse(screen.getByTestId("blocks").textContent ?? "[]") as AvailabilityBlock[];

describe("AvailabilityGrid", () => {
  it("toggles an hour on tap", () => {
    render(<Harness />);
    const cell = screen.getByRole("button", { name: "Monday 6 PM to 7 PM" });
    fireEvent.click(cell, { detail: 0 });
    expect(blocks()).toEqual([{ weekday: 0, start_time: "18:00:00", end_time: "19:00:00" }]);
    expect(cell).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(cell, { detail: 0 });
    expect(blocks()).toEqual([]);
  });

  it("joins neighbouring hours into one block", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Tuesday 7 PM to 8 PM" }), { detail: 0 });
    fireEvent.click(screen.getByRole("button", { name: "Tuesday 8 PM to 9 PM" }), { detail: 0 });
    expect(blocks()).toEqual([{ weekday: 1, start_time: "19:00:00", end_time: "21:00:00" }]);
  });

  it("works with the keyboard", async () => {
    render(<Harness />);
    const start = screen.getByRole("button", { name: "Monday 6 PM to 7 PM" });
    start.focus();
    await userEvent.keyboard("{ArrowRight}{ArrowDown} ");
    expect(screen.getByRole("button", { name: "Tuesday 7 PM to 8 PM" })).toHaveFocus();
    expect(blocks()).toEqual([{ weekday: 1, start_time: "19:00:00", end_time: "20:00:00" }]);
  });

  it("shows half-hour blocks as mixed", () => {
    render(<Harness initial={[{ weekday: 2, start_time: "18:00:00", end_time: "18:30:00" }]} />);
    expect(screen.getByRole("button", { name: "Wednesday 6 PM to 7 PM" })).toHaveAttribute(
      "aria-pressed",
      "mixed",
    );
  });
});

describe("availability helpers", () => {
  it("handles midnight ends and merges overlaps", () => {
    const late = { weekday: 4, start_time: "22:00:00", end_time: "00:00:00" };
    expect(totalHours([late])).toBe(2);
    expect(fromSlots(toSlots([late]))).toEqual([late]);
    const result = mergeBlocks([
      { weekday: 0, start_time: "18:00:00", end_time: "20:00:00" },
      { weekday: 0, start_time: "19:00:00", end_time: "21:00:00" },
    ]);
    expect(result).toEqual({
      blocks: [{ weekday: 0, start_time: "18:00:00", end_time: "21:00:00" }],
      merged: 1,
    });
  });
});

import { act, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("is disabled and shows the pending label while pending", () => {
    render(
      <Button pending pendingLabel="Saving…">
        Save
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Saving…" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("delays the spinner by 300 ms so fast requests do not flicker", () => {
    vi.useFakeTimers();
    const { container } = render(<Button pending>Save</Button>);
    expect(container.querySelector("svg")).toBeNull();
    act(() => vi.advanceTimersByTime(310));
    expect(container.querySelector("svg")).not.toBeNull();
    vi.useRealTimers();
  });
});

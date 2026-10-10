import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useInstall } from "@/lib/pwa";
import { InstallCard } from "./InstallCard";

const realAgent = navigator.userAgent;
afterEach(() => {
  useInstall.setState({ prompt: null, installed: false });
  Object.defineProperty(navigator, "userAgent", { value: realAgent, configurable: true });
});

describe("InstallCard", () => {
  it("says so when Leon is already installed", () => {
    useInstall.setState({ installed: true });
    render(<InstallCard />);
    expect(screen.getByText("Leon is installed on this device.")).toBeInTheDocument();
  });

  it("uses the browser's install offer when there is one", async () => {
    const prompt = vi.fn().mockResolvedValue(undefined);
    const offer = Object.assign(new Event("beforeinstallprompt"), {
      prompt,
      userChoice: Promise.resolve({ outcome: "accepted" as const }),
    });
    useInstall.setState({ prompt: offer });
    render(<InstallCard />);
    await userEvent.click(screen.getByRole("button", { name: "Install Leon" }));
    expect(prompt).toHaveBeenCalled();
    expect(useInstall.getState().installed).toBe(true);
  });

  it("gives Home Screen steps on iPhone", () => {
    Object.defineProperty(navigator, "userAgent", {
      value: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
      configurable: true,
    });
    render(<InstallCard />);
    expect(screen.getByText(/Add to Home Screen/)).toBeInTheDocument();
  });
});

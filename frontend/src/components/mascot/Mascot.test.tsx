import { render } from "@testing-library/react";
import { Mascot } from "./Mascot";

describe("Mascot", () => {
  it("shows the static illustration when reduced motion is requested", () => {
    const original = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      ...original(query),
      matches: query.includes("reduce"),
    })) as typeof window.matchMedia;
    const { container } = render(<Mascot mood="bad" size={80} />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
    window.matchMedia = original;
  });
});

describe("animation files", () => {
  const files = import.meta.glob("./animations/*.json", {
    eager: true,
    query: "?raw",
    import: "default",
  });
  it.each(Object.entries(files))("%s is under 150 KB", (_name, raw) => {
    expect((raw as string).length).toBeLessThan(150 * 1024);
  });
});

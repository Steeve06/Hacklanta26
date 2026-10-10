import { act, render } from "@testing-library/react";
import { Mascot } from "./Mascot";
import { MascotStill } from "./MascotStill";

function reduceMotion(on: boolean) {
  const original = window.matchMedia;
  window.matchMedia = ((query: string) => ({
    ...original(query),
    matches: on && query.includes("reduce"),
  })) as typeof window.matchMedia;
  return () => {
    window.matchMedia = original;
  };
}

describe("Mascot", () => {
  it("shows a still, decorative picture when reduced motion is requested", () => {
    const restore = reduceMotion(true);
    const { container } = render(<Mascot mood="bad" size={80} />);
    const img = container.querySelector("img");
    expect(img?.getAttribute("src")).toContain("voice-note");
    expect(img?.getAttribute("aria-hidden")).toBe("true");
    expect(img?.getAttribute("alt")).toBe("");
    restore();
  });

  it("plays a moment once, then returns to the mood", () => {
    vi.useFakeTimers();
    window.sessionStorage.clear();
    const { container } = render(
      <Mascot mood="good" moment={{ kind: "celebrate", key: "test-1" }} />,
    );
    expect(container.querySelector("img")?.getAttribute("src")).toContain("redemption");
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(container.querySelector("img")?.getAttribute("src")).toContain("calm");
    vi.useRealTimers();
  });

  it("maps moods to Leon's pictures", () => {
    const src = (el: HTMLElement) => el.querySelector("img")?.getAttribute("src");
    expect(src(render(<MascotStill mood="medium" />).container)).toContain("disappointed");
    expect(src(render(<MascotStill pose="nudge" />).container)).toContain("nudge");
  });
});

describe("pictures", () => {
  const files = import.meta.glob("./art/*.webp", { eager: true, query: "?url", import: "default" });
  it("has all seven poses", () => {
    expect(Object.keys(files)).toHaveLength(7);
  });
});

describe("picture sizes", () => {
  const inline = import.meta.glob("./art/*.webp", {
    eager: true,
    query: "?inline",
    import: "default",
  });
  it.each(Object.entries(inline))("%s is under 150 KB", (_name, dataUrl) => {
    const base64 = (dataUrl as string).split(",")[1] ?? "";
    expect((base64.length * 3) / 4).toBeLessThan(150 * 1024);
  });
});

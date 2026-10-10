import { fromLocalInputValue, localDateKey, relativeDue, toLocalInputValue } from "./time";

describe("time helpers", () => {
  it("round-trips a wall-clock input across a DST change", () => {
    const iso = fromLocalInputValue("2026-11-01T01:30", "America/New_York");
    expect(toLocalInputValue(iso, "America/New_York")).toBe("2026-11-01T01:30");
  });

  it("treats 23:59 as today and 00:00 as tomorrow in the student's zone", () => {
    expect(localDateKey("2026-10-10T03:59:00Z", "America/New_York")).toBe("2026-10-09");
    expect(localDateKey("2026-10-10T04:00:00Z", "America/New_York")).toBe("2026-10-10");
  });

  it("describes relative due times", () => {
    const now = new Date("2026-10-09T12:00:00Z");
    expect(relativeDue("2026-10-09T17:00:00Z", now)).toBe("in 5 h");
    expect(relativeDue("2026-10-12T12:00:00Z", now)).toBe("in 3 days");
    expect(relativeDue("2026-10-09T11:30:00Z", now)).toBe("30 min ago");
  });
});

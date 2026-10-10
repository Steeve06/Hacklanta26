import { describe, expect, it } from "vitest";
import type { OnboardingState } from "../api";
import { limitingChoice, plannableHours } from "./weeklyCapacity";

const allDay = Array.from({ length: 7 }, (_, weekday) => ({
  weekday,
  start_time: "08:00:00",
  end_time: "22:00:00",
}));

function state(blocks: typeof allDay, weekly: string, daily = "3.0"): OnboardingState {
  return {
    step: 5,
    completed_steps: [1, 2, 3, 4],
    version: 1,
    done: false,
    schedule_ready: true,
    availability: { blocks },
    preferences: {
      max_hours_per_day: daily,
      max_hours_per_week: weekly,
      session_minutes: 50,
      earliest_time: "08:00:00",
      latest_time: "22:00:00",
      timezone: "America/New_York",
    },
    notifications: { sass_level: 2, quiet_start: "22:00:00", quiet_end: "08:00:00" },
  } as OnboardingState;
}

describe("plannableHours", () => {
  it("is capped by the weekly limit when free time is plentiful", () => {
    const s = state(allDay, "10.0");
    expect(plannableHours(s)).toBe(10);
    expect(limitingChoice(s)).toBe("your weekly limit");
  });

  it("is capped by the daily maximum before the weekly limit", () => {
    const s = state(allDay, "40.0", "2.0");
    expect(plannableHours(s)).toBe(14);
    expect(limitingChoice(s)).toBe("your daily maximum and study window");
  });

  it("is capped by free time when little is marked", () => {
    const s = state([{ weekday: 0, start_time: "18:00:00", end_time: "20:00:00" }], "10.0");
    expect(plannableHours(s)).toBe(2);
    expect(limitingChoice(s)).toBe("your free time");
  });

  it("ignores free time outside the study window", () => {
    const s = state([{ weekday: 0, start_time: "06:00:00", end_time: "09:00:00" }], "10.0");
    expect(plannableHours(s)).toBe(1);
  });
});

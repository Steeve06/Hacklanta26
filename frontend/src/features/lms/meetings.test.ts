import { describe, expect, it } from "vitest";
import { campusNote, meetingLines, type Meeting } from "./meetings";

const meeting = (weekday: number, location = "Hartley Hall 120"): Meeting => ({
  weekday,
  start_time: "10:00:00",
  end_time: "11:15:00",
  location,
  timezone: "America/New_York",
});

describe("meetingLines", () => {
  it("groups days that share a time and room", () => {
    expect(meetingLines([meeting(0), meeting(2)])).toEqual([
      "Mon, Wed 10:00 AM–11:15 AM · Hartley Hall 120",
    ]);
    expect(meetingLines([meeting(0), meeting(4, "Lab B")])).toHaveLength(2);
  });

  it("notes campus time only for students in another zone", () => {
    expect(campusNote([meeting(0)], "America/New_York")).toBeNull();
    expect(campusNote([meeting(0)], "America/Chicago")).toMatch(/^Campus time \(/);
  });
});

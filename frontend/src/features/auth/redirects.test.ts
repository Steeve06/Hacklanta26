import { destinationAfterLogin, homeFor, safeNext } from "./redirects";

const student = (done: boolean) =>
  ({ role: "student", profile: { onboarding_done: done } }) as never;
const instructor = { role: "instructor", profile: null } as never;
const admin = { role: "admin", profile: null } as never;

describe("redirects", () => {
  it("sends each role home", () => {
    expect(homeFor(student(false))).toBe("/onboarding");
    expect(homeFor(student(true))).toBe("/pulse/today");
    expect(homeFor(instructor)).toBe("/teach");
    expect(homeFor(admin)).toBe("/lms");
  });

  it("returns to the page asked for unless onboarding or the role says otherwise", () => {
    expect(destinationAfterLogin(student(true), "/pulse/week")).toBe("/pulse/week");
    expect(destinationAfterLogin(student(false), "/pulse/week")).toBe("/onboarding");
    expect(destinationAfterLogin(instructor, "/pulse/week")).toBe("/teach");
    expect(destinationAfterLogin(instructor, "/lms/courses/4")).toBe("/lms/courses/4");
    expect(destinationAfterLogin(student(true), "/onboarding")).toBe("/pulse/today");
  });

  it("only accepts same-app paths", () => {
    expect(safeNext("https://evil.example")).toBeNull();
    expect(safeNext("//evil.example")).toBeNull();
    expect(safeNext("/login")).toBeNull();
    expect(safeNext("/pulse/checks/3")).toBe("/pulse/checks/3");
  });
});

import { passwordProblem, passwordRules } from "./passwordRules";

const ok = (password: string, email = "nia@example.edu", names = ["Nia", "Okoro"]) =>
  Object.fromEntries(passwordRules(password, email, names).map((r) => [r.id, r.ok]));

describe("passwordRules", () => {
  it("needs ten characters, not only digits, and nothing personal", () => {
    expect(ok("short")).toMatchObject({ length: false });
    expect(ok("12345678901")).toMatchObject({ length: true, numeric: false });
    expect(ok("okoro-river-lamp")).toMatchObject({ personal: false });
    expect(ok("maple-river-lantern")).toEqual({ length: true, numeric: true, personal: true });
  });

  it("names the first unmet rule", () => {
    expect(passwordProblem(passwordRules("abc", "a@b.co"))).toBe(
      "Password needs: at least 10 characters.",
    );
    expect(passwordProblem(passwordRules("maple-river-lantern", "a@b.co"))).toBeUndefined();
  });
});

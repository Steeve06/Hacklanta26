import { percent } from "./percent";

test("drops trailing zeros from decimal weights", () => {
  expect(percent("6.00")).toBe("6%");
  expect(percent("7.50")).toBe("7.5%");
  expect(percent(12.345)).toBe("12.35%");
});

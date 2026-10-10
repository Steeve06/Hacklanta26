// Windows and macOS treat names that differ only in letter case as the same file, so an
// import like "./PasswordRules" can load "passwordRules.ts" instead of the component.
test("no two source modules differ only by letter case", () => {
  const files = Object.keys(import.meta.glob("/src/**/*.{ts,tsx}"));
  const seen = new Map<string, string>();
  const clashes: string[] = [];
  for (const file of files) {
    const key = file.replace(/\.tsx?$/, "").toLowerCase();
    const other = seen.get(key);
    if (other) clashes.push(`${other} / ${file}`);
    seen.set(key, file);
  }
  expect(files.length).toBeGreaterThan(50);
  expect(clashes).toEqual([]);
});

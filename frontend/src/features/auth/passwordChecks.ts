export type Rule = { id: string; label: string; ok: boolean };

/** The checks the browser can make while you type. The server also rejects common passwords
 * and has the final say. */
export function passwordRules(password: string, email: string, names: string[] = []): Rule[] {
  const lower = password.toLowerCase();
  const personal = [email.split("@")[0] ?? "", ...names]
    .map((p) => p.trim().toLowerCase())
    .filter((p) => p.length >= 3);
  return [
    { id: "length", label: "At least 10 characters", ok: password.length >= 10 },
    {
      id: "numeric",
      label: "Not only numbers",
      ok: password.length > 0 && !/^\d+$/.test(password),
    },
    {
      id: "personal",
      label: "Doesn't contain your name or email",
      ok: password.length > 0 && !personal.some((p) => lower.includes(p)),
    },
  ];
}

export function passwordProblem(rules: Rule[]): string | undefined {
  const failed = rules.find((r) => !r.ok);
  return failed ? `Password needs: ${failed.label.toLowerCase()}.` : undefined;
}

import { Icon } from "@/components/Icon";
import { cx } from "@/lib/cx";
import type { Rule } from "./passwordRules";

export function PasswordRules({ id, rules }: { id: string; rules: Rule[] }) {
  return (
    <ul id={id} className="flex flex-col gap-1 text-sm" aria-label="Password rules">
      {rules.map((rule) => (
        <li
          key={rule.id}
          className={cx("flex items-center gap-2", rule.ok ? "text-pine-strong" : "text-ink-soft")}
        >
          <span
            aria-hidden="true"
            className={cx(
              "flex h-5 w-5 items-center justify-center rounded-full border",
              rule.ok ? "border-pine bg-pine-soft" : "border-line",
            )}
          >
            {rule.ok && <Icon name="check" className="h-3.5 w-3.5" />}
          </span>
          {rule.label}
          <span className="sr-only">{rule.ok ? "(done)" : "(not yet)"}</span>
        </li>
      ))}
    </ul>
  );
}

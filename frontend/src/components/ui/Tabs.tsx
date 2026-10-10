import { NavLink } from "react-router-dom";
import { cx } from "@/lib/cx";

type Tab = { to: string; label: string; end?: boolean };

export function RouteTabs({ tabs, label }: { tabs: Tab[]; label: string }) {
  return (
    <nav
      aria-label={label}
      className="-mx-4 overflow-x-auto border-b border-line px-4 md:mx-0 md:px-0"
    >
      <ul className="flex gap-1">
        {tabs.map((tab) => (
          <li key={tab.to}>
            <NavLink
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                cx(
                  "-mb-px inline-flex min-h-11 items-center border-b-[3px] px-3 font-bold transition-colors",
                  isActive
                    ? "border-pine text-ink"
                    : "border-transparent text-ink-soft hover:text-ink",
                )
              }
            >
              {tab.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

type Chip<T extends string> = { value: T; label: string };

export function ChipGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Chip<T>[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="radio"
          aria-checked={value === opt.value}
          onClick={() => onChange(opt.value)}
          className={cx(
            "min-h-11 rounded-full border px-4 text-sm font-bold transition-colors md:min-h-9",
            value === opt.value
              ? "border-ink bg-ink text-paper"
              : "border-line bg-surface text-ink-soft hover:text-ink",
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

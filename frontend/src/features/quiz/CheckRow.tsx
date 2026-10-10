import { Link } from "react-router-dom";
import { Icon } from "@/components/Icon";
import type { Check } from "./api";
import { TimeLeft } from "./TimeLeft";

/** An open check: what it covers and how long is left. */
export function OpenCheckRow({ check }: { check: Check }) {
  const started = check.tries_left < 2;
  return (
    <Link
      to={`/pulse/checks/${check.id}`}
      className="flex min-h-11 items-center justify-between gap-3 rounded-md border border-mustard bg-mustard-soft px-3 py-2 hover:border-ink-faint"
    >
      <span className="flex flex-col">
        <span className="font-bold">Study check: {check.title}</span>
        <span className="text-sm">
          {started ? "One try left" : `${check.card_count} cards`} ·{" "}
          <TimeLeft closesAt={check.closes_at} />
        </span>
      </span>
      <Icon name="chevron" className="h-5 w-5 text-ink-faint" />
    </Link>
  );
}

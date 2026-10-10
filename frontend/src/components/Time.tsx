import { formatExact, relativeDue, useTimezone } from "@/lib/time";

export function DueTime({ iso, prefix = "Due" }: { iso: string; prefix?: string }) {
  const tz = useTimezone();
  const exact = formatExact(iso, tz);
  return (
    <time dateTime={iso} title={exact} className="whitespace-nowrap">
      {prefix} {relativeDue(iso)}
      <span className="sr-only"> ({exact})</span>
    </time>
  );
}

export function ExactTime({ iso }: { iso: string }) {
  const tz = useTimezone();
  return <time dateTime={iso}>{formatExact(iso, tz)}</time>;
}

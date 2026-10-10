import { useMe } from "@/features/auth/hooks";

export function useTimezone(): string {
  const me = useMe();
  return me.data?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone;
}

const formatters = new Map<string, Intl.DateTimeFormat>();

function formatter(timeZone: string, options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = `${timeZone}|${JSON.stringify(options)}`;
  let found = formatters.get(key);
  if (!found) {
    found = new Intl.DateTimeFormat(undefined, { timeZone, ...options });
    formatters.set(key, found);
  }
  return found;
}

export function formatExact(iso: string, timeZone: string): string {
  return formatter(timeZone, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatDay(iso: string | Date, timeZone: string): string {
  return formatter(timeZone, { weekday: "long", month: "long", day: "numeric" }).format(
    new Date(iso),
  );
}

export function formatShortDay(iso: string | Date, timeZone: string): string {
  return formatter(timeZone, { weekday: "short", month: "short", day: "numeric" }).format(
    new Date(iso),
  );
}

export function formatTime(iso: string, timeZone: string): string {
  return formatter(timeZone, { hour: "numeric", minute: "2-digit" }).format(new Date(iso));
}

export function localDateKey(iso: string | Date, timeZone: string): string {
  return formatter(timeZone, { year: "numeric", month: "2-digit", day: "2-digit" })
    .formatToParts(new Date(iso))
    .reduce((acc, part) => {
      if (part.type === "year") return part.value + acc;
      if (part.type === "month") return `${acc}-${part.value}`;
      if (part.type === "day") return `${acc}-${part.value}`;
      return acc;
    }, "");
}

export function relativeDue(iso: string, now: Date = new Date()): string {
  const diffMs = new Date(iso).getTime() - now.getTime();
  const past = diffMs < 0;
  const minutes = Math.round(Math.abs(diffMs) / 60_000);
  let amount: string;
  if (minutes < 60) amount = `${Math.max(1, minutes)} min`;
  else if (minutes < 60 * 48) amount = `${Math.round(minutes / 60)} h`;
  else amount = `${Math.round(minutes / 60 / 24)} days`;
  return past ? `${amount} ago` : `in ${amount}`;
}

export function toLocalInputValue(iso: string, timeZone: string): string {
  const parts = Object.fromEntries(
    formatter(timeZone, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(new Date(iso))
      .map((p) => [p.type, p.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function fromLocalInputValue(value: string, timeZone: string): string {
  const guess = new Date(`${value}:00Z`);
  const asLocal = toLocalInputValue(guess.toISOString(), timeZone);
  const offsetMs = new Date(`${asLocal}:00Z`).getTime() - guess.getTime();
  return new Date(guess.getTime() - offsetMs).toISOString();
}

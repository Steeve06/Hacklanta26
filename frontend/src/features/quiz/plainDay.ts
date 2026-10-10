/** Format a plain `YYYY-MM-DD` day without shifting it through the viewer's timezone. */
export function formatPlainDay(day: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(undefined, { ...options, timeZone: "UTC" }).format(
    new Date(`${day}T12:00:00Z`),
  );
}

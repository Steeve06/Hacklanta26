/** "6.00" → "6", "7.50" → "7.5". Weights arrive as decimal strings. */
export function percent(value: string | number): string {
  return `${Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 })}%`;
}

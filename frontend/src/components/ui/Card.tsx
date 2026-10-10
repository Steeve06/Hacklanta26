import type { HTMLAttributes } from "react";
import { cx } from "@/lib/cx";

export function Card({ className, ...rest }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cx("rounded-lg border border-line bg-surface p-4 md:p-5", className)}
      {...rest}
    />
  );
}

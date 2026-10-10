import { cx } from "@/lib/cx";
import { useDelayed } from "@/lib/useDelayed";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cx("animate-pulse rounded-sm bg-sunken motion-reduce:animate-none", className)}
    />
  );
}

export function SkeletonLines({ lines = 3 }: { lines?: number }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cx("h-4", i === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

export function DelayedSkeleton({
  children,
  label = "Loading",
}: {
  children: React.ReactNode;
  label?: string;
}) {
  const visible = useDelayed(true);
  return (
    <div role="status" aria-live="polite" className="min-h-24">
      <span className="sr-only">{label}</span>
      {visible && children}
    </div>
  );
}

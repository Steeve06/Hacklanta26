import { Skeleton, TopProgress } from "@/components/ui";

export function AppSkeleton() {
  return (
    <div className="min-h-dvh md:pl-60" role="status" aria-label="Loading Pulse">
      <TopProgress active />
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col gap-3 border-r border-line bg-surface p-5 md:flex">
        <Skeleton className="h-8 w-24" />
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </aside>
      <main className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-6 md:px-8">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-24 w-full" />
      </main>
    </div>
  );
}

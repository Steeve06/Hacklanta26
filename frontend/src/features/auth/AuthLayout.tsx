import type { ReactNode } from "react";
import { MascotStill } from "@/components/mascot/MascotStill";
import { TopProgress } from "@/components/ui";

export function AuthLayout({
  title,
  busy = false,
  children,
}: {
  title: string;
  busy?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="min-h-dvh bg-paper">
      <TopProgress active={busy} />
      <main className="mx-auto grid min-h-dvh max-w-5xl items-center gap-8 px-4 py-10 md:grid-cols-[1fr_minmax(0,26rem)] md:gap-10 md:px-8">
        <div className="flex flex-col gap-4">
          <MascotStill mood="good" size={96} />
          <p className="font-display text-3xl font-extrabold">Leon</p>
          <p className="max-w-md text-lg text-ink-soft">
            Your courses, your deadlines and one very invested study buddy who will notice if you
            skip.
          </p>
        </div>
        <section
          aria-labelledby="auth-title"
          className="rounded-lg border border-line bg-surface p-5 md:p-6"
        >
          <h1 id="auth-title" className="mb-4 text-xl font-bold">
            {title}
          </h1>
          {children}
        </section>
      </main>
    </div>
  );
}

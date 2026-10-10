import { Outlet } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { TopProgress } from "@/components/ui";
import { useLogout, useMe } from "@/features/auth/hooks";

export function OnboardingLayout() {
  const me = useMe();
  const logout = useLogout();
  return (
    <div className="min-h-dvh bg-paper">
      <TopProgress />
      <header className="flex items-center justify-between border-b border-line bg-surface px-4 py-2 md:px-8">
        <span className="font-display text-xl font-extrabold text-pine">Pulse</span>
        <div className="flex items-center gap-2">
          <span className="hidden text-sm text-ink-soft sm:inline">{me.data?.email}</span>
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="flex min-h-11 items-center gap-2 rounded-md px-3 text-sm font-bold text-ink-soft hover:bg-sunken hover:text-ink"
          >
            <Icon name="signout" />
            Sign out
          </button>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-3xl px-4 pb-16 pt-6 md:px-8">
        <Outlet />
      </main>
    </div>
  );
}

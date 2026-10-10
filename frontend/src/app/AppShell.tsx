import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Icon, type IconName } from "@/components/Icon";
import { TopProgress } from "@/components/ui";
import { AssistantPanel } from "@/features/assistant/AssistantPanel";
import { useLogout, useMe } from "@/features/auth/hooks";
import { useInbox } from "@/features/notifications/api";
import { cx } from "@/lib/cx";
import { ShellExtras } from "./ShellExtras";

type NavItem = {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
  mobile?: boolean;
  /** Label in the phone's bottom bar, where space is tight. */
  short?: string;
  external?: boolean;
};

const studentNav: NavItem[] = [
  { to: "/pulse/today", label: "Today", icon: "today", mobile: true },
  { to: "/pulse/week", label: "Week", icon: "week", mobile: true },
  { to: "/pulse/checks", label: "Study checks", short: "Checks", icon: "quiz", mobile: true },
  { to: "/pulse/leaderboard", label: "Leaderboard", short: "Ranks", icon: "trophy", mobile: true },
  { to: "/lms", label: "Courses", icon: "courses", mobile: true },
  { to: "/settings", label: "Settings", icon: "settings" },
];

const instructorNav: NavItem[] = [
  { to: "/lms", label: "Courses", icon: "courses", mobile: true },
  { to: "/settings", label: "Settings", icon: "settings", mobile: true },
];

const adminNav: NavItem[] = [
  { to: "/lms", label: "Courses", icon: "courses", mobile: true },
  { to: "/demo", label: "Demo controls", icon: "roster", mobile: true },
  { to: "/admin/", label: "Django admin", icon: "external", mobile: true, external: true },
  { to: "/settings", label: "Settings", icon: "settings", mobile: true },
];

function navFor(role: string | undefined, demoMode: boolean): NavItem[] {
  if (role === "instructor") return instructorNav;
  if (role === "admin") return demoMode ? adminNav : adminNav.filter((i) => i.to !== "/demo");
  return studentNav;
}

export function AppShell() {
  const me = useMe();
  const logout = useLogout();
  const items = navFor(me.data?.role, Boolean(me.data?.demo_mode));
  const isStudent = me.data?.role === "student";
  const canAsk = isStudent && Boolean(me.data?.profile.onboarding_done);
  const [asking, setAsking] = useState(false);

  return (
    <div className="min-h-dvh md:pl-60">
      <TopProgress />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface focus:p-3"
      >
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-line bg-surface md:flex">
        <div className="flex shrink-0 items-center justify-between px-5 py-5">
          <span className="font-display text-2xl font-extrabold text-pine">Leon</span>
          {isStudent && <InboxLink />}
        </div>
        <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
          <ul className="flex flex-col gap-1">
            {items.map((item) => (
              <li key={item.to}>
                <NavEntry
                  item={item}
                  className={(isActive) =>
                    cx(
                      "flex min-h-11 items-center gap-3 rounded-md px-3 font-bold transition-colors",
                      isActive
                        ? "bg-pine-soft text-pine-strong"
                        : "text-ink-soft hover:bg-sunken hover:text-ink",
                    )
                  }
                />
              </li>
            ))}
          </ul>
          {canAsk && (
            <button
              type="button"
              onClick={() => setAsking(true)}
              aria-haspopup="dialog"
              className="mt-4 flex min-h-11 w-full items-center gap-3 rounded-md border border-line px-3 font-bold text-ink hover:bg-sunken"
            >
              <Icon name="chat" />
              Ask Leon
            </button>
          )}
        </nav>
        <div className="shrink-0 border-t border-line p-3">
          <p className="truncate px-3 pb-2 text-sm text-ink-soft">{me.data?.email}</p>
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="flex min-h-11 w-full items-center gap-3 rounded-md px-3 font-bold text-ink-soft hover:bg-sunken hover:text-ink"
          >
            <Icon name="signout" />
            Sign out
          </button>
        </div>
      </aside>

      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-surface/95 px-4 py-2 backdrop-blur md:hidden">
        <span className="font-display text-xl font-extrabold text-pine">Leon</span>
        <div className="flex items-center">
          {canAsk && (
            <button
              type="button"
              onClick={() => setAsking(true)}
              aria-haspopup="dialog"
              className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md hover:bg-sunken"
            >
              <Icon name="chat" label="Ask Leon" />
            </button>
          )}
          {isStudent && <InboxLink />}
          {isStudent && (
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                cx(
                  "inline-flex min-h-11 min-w-11 items-center justify-center rounded-md hover:bg-sunken",
                  isActive && "text-pine",
                )
              }
            >
              <Icon name="settings" label="Settings" />
            </NavLink>
          )}
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-5xl px-4 pb-28 pt-5 md:px-8 md:pb-12 md:pt-8">
        <Outlet />
      </main>

      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface md:hidden"
      >
        <ul className="flex">
          {items
            .filter((item) => item.mobile)
            .map((item) => (
              <li key={item.to} className="flex-1">
                <NavEntry
                  compact
                  item={item}
                  className={(isActive) =>
                    cx(
                      "flex min-h-14 flex-col items-center justify-center gap-0.5 text-xs font-bold",
                      isActive ? "text-pine" : "text-ink-soft",
                    )
                  }
                />
              </li>
            ))}
        </ul>
      </nav>
      {isStudent && <ShellExtras />}
      {canAsk && <AssistantPanel open={asking} onClose={() => setAsking(false)} />}
    </div>
  );
}

function NavEntry({
  item,
  className,
  compact = false,
}: {
  item: NavItem;
  className: (isActive: boolean) => string;
  compact?: boolean;
}) {
  const label = compact ? (item.short ?? item.label) : item.label;
  if (item.external)
    return (
      <a href={item.to} className={className(false)}>
        <Icon name={item.icon} />
        {label}
      </a>
    );
  return (
    <NavLink to={item.to} end={item.end} className={({ isActive }) => className(isActive)}>
      <Icon name={item.icon} />
      {label}
    </NavLink>
  );
}

function InboxLink() {
  return (
    <NavLink
      to="/pulse/inbox"
      className={({ isActive }) =>
        cx(
          "relative inline-flex min-h-11 min-w-11 items-center justify-center rounded-md hover:bg-sunken",
          isActive && "text-pine",
        )
      }
    >
      <Icon name="bell" label="Notifications" />
      <UnreadDot />
    </NavLink>
  );
}

function UnreadDot() {
  const inbox = useInbox();
  const unread = inbox.data?.unread ?? 0;
  if (!unread) return null;
  return (
    <span className="absolute right-1.5 top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-berry px-1 text-xs font-bold text-white">
      {unread > 9 ? "9+" : unread}
      <span className="sr-only"> unread</span>
    </span>
  );
}

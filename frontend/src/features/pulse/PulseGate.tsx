import { Navigate, Outlet } from "react-router-dom";
import { Skeleton } from "@/components/ui";
import { useMe } from "@/features/auth/hooks";
import { homeFor, needsOnboarding, ONBOARDING } from "@/features/auth/redirects";

/** Pulse pages are for students who finished onboarding. */
export function PulseGate() {
  const me = useMe();
  if (me.isPending) return <Skeleton className="h-96 w-full" />;
  if (!me.data) return <Navigate to="/" replace />;
  if (me.data.role !== "student") return <Navigate to={homeFor(me.data)} replace />;
  if (needsOnboarding(me.data)) return <Navigate to={ONBOARDING} replace />;
  return <Outlet />;
}

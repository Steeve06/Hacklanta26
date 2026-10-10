import { Navigate, Outlet } from "react-router-dom";
import { AppSkeleton } from "@/app/AppSkeleton";
import { useMe } from "@/features/auth/hooks";
import { homeFor, needsOnboarding } from "@/features/auth/redirects";

/** Only students who haven't finished onboarding see it. */
export function OnboardingGate() {
  const me = useMe();
  if (me.isPending) return <AppSkeleton />;
  if (!me.data) return <Navigate to="/" replace />;
  if (!needsOnboarding(me.data)) return <Navigate to={homeFor(me.data)} replace />;
  return <Outlet />;
}

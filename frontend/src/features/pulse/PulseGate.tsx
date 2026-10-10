import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Skeleton } from "@/components/ui";
import { useMe } from "@/features/auth/hooks";

export function PulseGate() {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <Skeleton className="h-96 w-full" />;
  if (me.data?.role !== "student") return <Navigate to="/lms" replace />;
  if (!me.data.profile?.onboarding_done && location.pathname !== "/pulse/onboarding") {
    return <Navigate to="/pulse/onboarding" replace />;
  }
  return <Outlet />;
}

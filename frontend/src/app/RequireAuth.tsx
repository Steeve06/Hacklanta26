import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useBootstrapSession } from "@/features/auth/hooks";
import { useAuth } from "@/features/auth/store";
import { AppSkeleton } from "./AppSkeleton";

export function RequireAuth() {
  const status = useAuth((s) => s.status);
  const bootstrap = useBootstrapSession();
  const location = useLocation();
  if (status === "unknown" || (bootstrap.isPending && status !== "signed-in"))
    return <AppSkeleton />;
  if (status === "signed-out") {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <Outlet />;
}

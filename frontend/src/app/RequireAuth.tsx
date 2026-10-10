import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useBootstrapSession } from "@/features/auth/hooks";
import { useAuth } from "@/features/auth/store";
import { AppSkeleton } from "./AppSkeleton";
import { ServerUnreachable } from "./ServerUnreachable";

/** Signed-in pages. While the session is being restored, show the app's skeleton, not the
 * sign-in form; if the server can't be reached, say so instead of signing the user out. */
export function RequireAuth() {
  const status = useAuth((s) => s.status);
  const bootstrap = useBootstrapSession();
  const location = useLocation();
  if (status === "signed-in") return <Outlet />;
  if (bootstrap.isPending || (status === "unknown" && bootstrap.data !== "offline"))
    return <AppSkeleton />;
  if (bootstrap.data === "offline")
    return (
      <ServerUnreachable onRetry={() => void bootstrap.refetch()} retrying={bootstrap.isFetching} />
    );
  const next = encodeURIComponent(location.pathname + location.search);
  return <Navigate to={`/login?next=${next}`} replace />;
}

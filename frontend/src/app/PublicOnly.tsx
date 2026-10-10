import { Outlet } from "react-router-dom";
import { useBootstrapSession } from "@/features/auth/hooks";
import { useAuth } from "@/features/auth/store";
import { AppSkeleton } from "./AppSkeleton";
import { HomeRedirect } from "./HomeRedirect";

/** Sign-in and sign-up. Someone already signed in goes to their home page instead. */
export function PublicOnly() {
  const status = useAuth((s) => s.status);
  const bootstrap = useBootstrapSession();
  if (status === "signed-in") return <HomeRedirect />;
  if (status === "unknown" && bootstrap.isPending) return <AppSkeleton />;
  return <Outlet />;
}

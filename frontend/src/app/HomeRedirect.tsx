import { Navigate } from "react-router-dom";
import { useMe } from "@/features/auth/hooks";
import { AppSkeleton } from "./AppSkeleton";

export function HomeRedirect() {
  const me = useMe();
  if (me.isPending) return <AppSkeleton />;
  if (me.data?.role === "admin" && me.data.demo_mode) return <Navigate to="/demo" replace />;
  if (me.data?.role === "student") return <Navigate to="/pulse" replace />;
  return <Navigate to="/lms" replace />;
}

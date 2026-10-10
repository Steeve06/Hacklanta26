import { Navigate } from "react-router-dom";
import { ErrorState } from "@/components/ui";
import { errorMessage } from "@/api/client";
import { useMe } from "@/features/auth/hooks";
import { homeFor } from "@/features/auth/redirects";
import { AppSkeleton } from "./AppSkeleton";

export function HomeRedirect() {
  const me = useMe();
  if (me.isPending) return <AppSkeleton />;
  if (me.isError)
    return (
      <div className="p-6">
        <ErrorState message={errorMessage(me.error)} onRetry={() => void me.refetch()} />
      </div>
    );
  return <Navigate to={homeFor(me.data)} replace />;
}

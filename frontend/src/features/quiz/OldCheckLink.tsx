import { Navigate, useParams } from "react-router-dom";

/** Reminders sent before study checks moved to /pulse/checks still link to /pulse/quiz/:id. */
export function OldCheckLink() {
  const { checkId } = useParams();
  return <Navigate to={checkId ? `/pulse/checks/${checkId}` : "/pulse/checks"} replace />;
}

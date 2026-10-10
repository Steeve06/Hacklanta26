import type { Session } from "./api";

export function sessionLink(session: Session, courseId: number): string {
  if (session.kind === "chapter_quiz") return "/pulse/checks";
  if (session.source_type === "chapter")
    return `/lms/courses/${courseId}/chapters/${session.source_id}`;
  return `/lms/courses/${courseId}/assignments/${session.source_id}`;
}

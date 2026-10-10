import type { Quiz } from "./api";

export function quizName(quiz: Pick<Quiz, "chapters">): string {
  return quiz.chapters.map((c) => `${c.course_code} Ch ${c.order}`).join(" · ") || "Chapter quiz";
}

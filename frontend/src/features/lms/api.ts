import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type Course = Schemas["Course"];
export type ChapterSummary = Schemas["ChapterList"];
export type ChapterDetail = Schemas["ChapterDetail"];
export type Assessment = Schemas["Assessment"];
export type AssessmentDetail = Schemas["AssessmentDetail"];
export type Syllabus = Schemas["Syllabus"];
export type Discussion = Schemas["Discussion"];
export type QuizAttempt = Schemas["QuizAttempt"];
export type RosterRow = Schemas["RosterRow"];
export type AssessmentWrite = Schemas["AssessmentWriteRequest"];
export type ChapterWrite = Schemas["ChapterWriteRequest"];
export type QuestionWrite = Schemas["QuestionWrite"];

export const lmsKeys = {
  courses: ["courses"] as const,
  course: (id: number) => ["courses", id] as const,
  chapters: (courseId: number) => ["courses", courseId, "chapters"] as const,
  chapter: (id: number) => ["chapters", id] as const,
  assessments: (courseId: number) => ["courses", courseId, "assessments"] as const,
  assessment: (id: number) => ["assessments", id] as const,
  questions: (id: number) => ["assessments", id, "questions"] as const,
  discussion: (id: number) => ["assessments", id, "posts"] as const,
  roster: (id: number) => ["assessments", id, "roster"] as const,
  syllabus: (courseId: number) => ["courses", courseId, "syllabus"] as const,
  attempt: (id: number) => ["attempts", id] as const,
};

export function useCourses() {
  return useQuery({
    queryKey: lmsKeys.courses,
    queryFn: async () => unwrap(await api.GET("/api/v1/courses")),
  });
}

export function useCourse(id: number) {
  return useQuery({
    queryKey: lmsKeys.course(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/courses/{course_id}", { params: { path: { course_id: id } } })),
  });
}

export function useChapters(courseId: number) {
  return useQuery({
    queryKey: lmsKeys.chapters(courseId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/courses/{course_id}/chapters", {
          params: { path: { course_id: courseId } },
        }),
      ),
  });
}

export function useChapter(id: number) {
  return useQuery({
    queryKey: lmsKeys.chapter(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/chapters/{chapter_id}", { params: { path: { chapter_id: id } } }),
      ),
  });
}

export function useCompleteChapter(courseId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (chapterId: number) =>
      unwrap(
        await api.POST("/api/v1/chapters/{chapter_id}/complete", {
          params: { path: { chapter_id: chapterId } },
        }),
      ),
    onMutate: async (chapterId) => {
      await client.cancelQueries({ queryKey: lmsKeys.chapter(chapterId) });
      const previous = client.getQueryData<ChapterDetail>(lmsKeys.chapter(chapterId));
      if (previous)
        client.setQueryData(lmsKeys.chapter(chapterId), {
          ...previous,
          completed_at: new Date().toISOString(),
        });
      return { previous };
    },
    onError: (_error, chapterId, context) => {
      if (context?.previous) client.setQueryData(lmsKeys.chapter(chapterId), context.previous);
    },
    onSettled: (_data, _error, chapterId) => {
      void client.invalidateQueries({ queryKey: lmsKeys.chapter(chapterId) });
      void client.invalidateQueries({ queryKey: lmsKeys.chapters(courseId) });
      void client.invalidateQueries({ queryKey: lmsKeys.courses });
      void client.invalidateQueries({ queryKey: ["pulse"] });
      void client.invalidateQueries({ queryKey: ["quizzes"] });
    },
  });
}

export function useAssessments(courseId: number) {
  return useQuery({
    queryKey: lmsKeys.assessments(courseId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/courses/{course_id}/assessments", {
          params: { path: { course_id: courseId } },
        }),
      ),
  });
}

export function useAssessment(id: number) {
  return useQuery({
    queryKey: lmsKeys.assessment(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/assessments/{assessment_id}", {
          params: { path: { assessment_id: id } },
        }),
      ),
  });
}

export function useSyllabus(courseId: number) {
  return useQuery({
    queryKey: lmsKeys.syllabus(courseId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/courses/{course_id}/syllabus", {
          params: { path: { course_id: courseId } },
        }),
      ),
  });
}

export function useDiscussion(id: number) {
  return useQuery({
    queryKey: lmsKeys.discussion(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/assessments/{assessment_id}/posts", {
          params: { path: { assessment_id: id } },
        }),
      ),
  });
}

export function useInvalidateAssessment() {
  const client = useQueryClient();
  return (assessment: { id: number; course: number }) => {
    void client.invalidateQueries({ queryKey: lmsKeys.assessment(assessment.id) });
    void client.invalidateQueries({ queryKey: lmsKeys.assessments(assessment.course) });
    void client.invalidateQueries({ queryKey: lmsKeys.discussion(assessment.id) });
    void client.invalidateQueries({ queryKey: lmsKeys.roster(assessment.id) });
    void client.invalidateQueries({ queryKey: lmsKeys.courses });
    void client.invalidateQueries({ queryKey: ["pulse"] });
  };
}

export function usePostToDiscussion(assessment: { id: number; course: number }) {
  const invalidate = useInvalidateAssessment();
  return useMutation({
    mutationFn: async (body: { body: string; parent?: number | null }) =>
      unwrap(
        await api.POST("/api/v1/assessments/{assessment_id}/posts", {
          params: { path: { assessment_id: assessment.id } },
          body,
        }),
      ),
    onSuccess: () => invalidate(assessment),
  });
}

export function useStartAttempt() {
  return useMutation({
    mutationFn: async (assessmentId: number) =>
      unwrap(
        await api.POST("/api/v1/assessments/{assessment_id}/attempts", {
          params: { path: { assessment_id: assessmentId } },
        }),
      ),
  });
}

export function useAttempt(id: number) {
  return useQuery({
    queryKey: lmsKeys.attempt(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/attempts/{attempt_id}", { params: { path: { attempt_id: id } } }),
      ),
  });
}

export function useSaveAnswers(attemptId: number) {
  return useMutation({
    mutationFn: async (answers: Record<string, number>) =>
      unwrap(
        await api.PATCH("/api/v1/attempts/{attempt_id}", {
          params: { path: { attempt_id: attemptId } },
          body: { answers },
        }),
      ),
  });
}

export function useSubmitAttempt(attemptId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (answers: Record<string, number>) =>
      unwrap(
        await api.POST("/api/v1/attempts/{attempt_id}/submit", {
          params: { path: { attempt_id: attemptId } },
          body: { answers },
        }),
      ),
    onSuccess: (attempt) => {
      client.setQueryData(lmsKeys.attempt(attemptId), attempt);
      void client.invalidateQueries({ queryKey: lmsKeys.assessment(attempt.assessment) });
      void client.invalidateQueries({ queryKey: ["courses"] });
      void client.invalidateQueries({ queryKey: ["pulse"] });
    },
  });
}

export function useRoster(id: number, enabled: boolean) {
  return useQuery({
    queryKey: lmsKeys.roster(id),
    enabled,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/assessments/{assessment_id}/roster", {
          params: { path: { assessment_id: id } },
        }),
      ),
  });
}

export function useQuestions(id: number, enabled: boolean) {
  return useQuery({
    queryKey: lmsKeys.questions(id),
    enabled,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/assessments/{assessment_id}/questions", {
          params: { path: { assessment_id: id } },
        }),
      ),
  });
}

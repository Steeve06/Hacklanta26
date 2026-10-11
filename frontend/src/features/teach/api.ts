import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { lmsKeys } from "@/features/lms/api";

type Schemas = components["schemas"];
export type TeachingCourse = Schemas["TeachingCourse"];
export type RegisteredCourse = Schemas["RegisteredCourse"];
export type Registration = Schemas["RegistrationRequest"];
export type SyllabusUpdate = Schemas["PatchedSyllabusUpdateRequest"];

export const teachKeys = {
  overview: ["teach", "overview"] as const,
  registrations: ["teach", "registrations"] as const,
};

export function useTeachingOverview() {
  return useQuery({
    queryKey: teachKeys.overview,
    queryFn: async () => unwrap(await api.GET("/api/v1/teach/overview")),
  });
}

export function useRegistrations() {
  return useQuery({
    queryKey: teachKeys.registrations,
    queryFn: async () => unwrap(await api.GET("/api/v1/teach/registrations")),
  });
}

export function useRegisterCourse() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: Registration) =>
      unwrap(await api.POST("/api/v1/teach/registrations", { body })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: teachKeys.registrations });
      void client.invalidateQueries({ queryKey: lmsKeys.courses });
    },
  });
}

export function useUpdateSyllabus(courseId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: SyllabusUpdate) =>
      unwrap(
        await api.PATCH("/api/v1/courses/{course_id}/syllabus/edit", {
          params: { path: { course_id: courseId } },
          body,
        }),
      ),
    onSuccess: (data) => client.setQueryData(lmsKeys.syllabus(courseId), data),
  });
}

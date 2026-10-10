import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type Schedule = Schemas["Schedule"];
export type Session = Schemas["Session"];
export type Deadline = Schemas["Deadline"];
export type AvailabilityBlock = Schemas["AvailabilityBlock"];
export type Blackout = Schemas["Blackout"];
export type PlanJob = Schemas["PlanJob"];
export type OverloadReport = Schemas["OverloadReport"];
export type CourseCalendar = Schemas["CourseCalendar"];
export type ChapterRelease = Schemas["ChapterRelease"];
export type ScheduleView = "today" | "week" | "overall";

export const pulseKeys = {
  all: ["pulse"] as const,
  schedule: (view: ScheduleView, from?: string) =>
    ["pulse", "schedule", view, from ?? "now"] as const,
  availability: ["pulse", "availability"] as const,
  blackouts: ["pulse", "blackouts"] as const,
  job: (id: number) => ["pulse", "job", id] as const,
  latestJob: ["pulse", "job", "latest"] as const,
};

export function useSchedule(view: ScheduleView, from?: string, enabled = true) {
  return useQuery({
    queryKey: pulseKeys.schedule(view, from),
    enabled,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/pulse/schedule", {
          params: { query: { view, ...(from ? { from } : {}) } },
        }),
      ),
    refetchInterval: 60_000,
  });
}

export function useCourseCalendar(from: string) {
  return useQuery({
    queryKey: ["pulse", "course-calendar", from],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/pulse/course-calendar", { params: { query: { from } } })),
  });
}

export function useAvailability() {
  return useQuery({
    queryKey: pulseKeys.availability,
    queryFn: async () => unwrap(await api.GET("/api/v1/pulse/availability")),
  });
}

export function useSaveAvailability() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (blocks: AvailabilityBlock[]) =>
      unwrap(await api.PUT("/api/v1/pulse/availability", { body: { blocks } })),
    onSuccess: (data) => {
      client.setQueryData(pulseKeys.availability, data);
      void client.invalidateQueries({ queryKey: ["pulse", "schedule"] });
    },
  });
}

export function useBlackouts() {
  return useQuery({
    queryKey: pulseKeys.blackouts,
    queryFn: async () => unwrap(await api.GET("/api/v1/pulse/blackouts")),
  });
}

export function useAddBlackout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { start: string; end: string; label: string }) =>
      unwrap(await api.POST("/api/v1/pulse/blackouts", { body })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: pulseKeys.blackouts });
      void client.invalidateQueries({ queryKey: ["pulse", "schedule"] });
    },
  });
}

export function useDeleteBlackout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.DELETE("/api/v1/pulse/blackouts/{blackout_id}", {
        params: { path: { blackout_id: id } },
      });
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: pulseKeys.blackouts });
      void client.invalidateQueries({ queryKey: ["pulse", "schedule"] });
    },
  });
}

export function useGenerate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (feedback?: string) =>
      unwrap(
        await api.POST("/api/v1/pulse/schedules/generate", {
          body: feedback === undefined ? {} : { feedback },
        }),
      ),
    onSuccess: (job) => client.setQueryData(pulseKeys.latestJob, job),
  });
}

export function useLatestJob() {
  return useQuery({
    queryKey: pulseKeys.latestJob,
    queryFn: async () => {
      const result = await api.GET("/api/v1/pulse/jobs/latest");
      if (result.response.status === 404) return null;
      return unwrap(result);
    },
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state === "queued" || state === "running" ? 700 : false;
    },
  });
}

export function useCancelJob() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.POST("/api/v1/pulse/jobs/{job_id}/cancel", { params: { path: { job_id: id } } }),
      ),
    onSuccess: (job) => client.setQueryData(pulseKeys.latestJob, job),
  });
}

type SessionUpdate = {
  id: number;
  status: "done" | "partial" | "skipped" | "planned";
  completed_minutes?: number;
};

export function useUpdateSession() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: SessionUpdate) =>
      unwrap(
        await api.PATCH("/api/v1/pulse/sessions/{session_id}", {
          params: { path: { session_id: id } },
          body,
        }),
      ),
    onMutate: async (update) => {
      await client.cancelQueries({ queryKey: ["pulse", "schedule"] });
      const snapshots = client.getQueriesData<Schedule>({ queryKey: ["pulse", "schedule"] });
      for (const [key, data] of snapshots) {
        if (!data) continue;
        client.setQueryData<Schedule>(key, {
          ...data,
          sessions: data.sessions.map((s) =>
            s.id === update.id ? { ...s, status: update.status } : s,
          ),
        });
      }
      return { snapshots };
    },
    onError: (_err, _update, context) => {
      for (const [key, data] of context?.snapshots ?? []) client.setQueryData(key, data);
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: pulseKeys.all });
    },
  });
}

export function useRescheduleSession() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.POST("/api/v1/pulse/sessions/{session_id}/reschedule", {
          params: { path: { session_id: id } },
        }),
      ),
    onSettled: () => void client.invalidateQueries({ queryKey: pulseKeys.all }),
  });
}

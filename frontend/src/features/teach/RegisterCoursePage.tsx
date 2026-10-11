import { useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "@/api/client";
import { Button, Input, QueryView, Select, SkeletonLines, Textarea, toast } from "@/components/ui";
import { useRegisterCourse, useRegistrations } from "./api";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

type MeetingDraft = { weekday: string; start_time: string; end_time: string; location: string };

const blank = {
  code: "",
  title: "",
  teacher_email: "",
  teacher_first_name: "",
  teacher_last_name: "",
  color: "#1f6f5c",
  description: "",
  office_hours: "",
};

export function RegisterCoursePage() {
  const registrations = useRegistrations();
  const register = useRegisterCourse();
  const [form, setForm] = useState(blank);
  const [meetings, setMeetings] = useState<MeetingDraft[]>([]);
  const fields = register.error instanceof ApiError ? register.error.fields : {};
  const set = (key: keyof typeof blank) => (e: { target: { value: string } }) =>
    setForm({ ...form, [key]: e.target.value });

  function submit(e: FormEvent) {
    e.preventDefault();
    register.mutate(
      {
        ...form,
        meetings: meetings.map((m) => ({ ...m, weekday: Number(m.weekday) })),
      },
      {
        onSuccess: (course) => {
          toast.success(`${course.code} registered. ${course.teacher_email} can sign up now.`);
          setForm(blank);
          setMeetings([]);
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  return (
    <div className="flex max-w-3xl flex-col gap-8">
      <header>
        <h1 className="text-2xl font-bold">Register courses</h1>
        <p className="text-ink-soft">
          Register a course with its teacher&apos;s email. The teacher signs up with that email,
          chooses &quot;I teach a course&quot;, and finds the course ready for content.
        </p>
      </header>
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-[10rem_1fr_6rem]">
          <Input label="Code" value={form.code} onChange={set("code")} error={fields.code?.[0]} />
          <Input
            label="Title"
            value={form.title}
            onChange={set("title")}
            error={fields.title?.[0]}
          />
          <Input label="Color" type="color" value={form.color} onChange={set("color")} />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Input
            label="Teacher email"
            type="email"
            value={form.teacher_email}
            onChange={set("teacher_email")}
            error={fields.teacher_email?.[0]}
          />
          <Input
            label="First name (optional)"
            value={form.teacher_first_name}
            onChange={set("teacher_first_name")}
          />
          <Input
            label="Last name (optional)"
            value={form.teacher_last_name}
            onChange={set("teacher_last_name")}
          />
        </div>
        <Textarea
          label="Course description"
          value={form.description}
          onChange={set("description")}
          rows={3}
        />
        <Input label="Office hours" value={form.office_hours} onChange={set("office_hours")} />
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-2 font-bold">Class times</legend>
          {meetings.map((m, i) => {
            const update = (patch: Partial<MeetingDraft>) =>
              setMeetings(meetings.map((x, j) => (j === i ? { ...x, ...patch } : x)));
            return (
              <div key={i} className="grid items-end gap-2 sm:grid-cols-[9rem_7rem_7rem_1fr_auto]">
                <Select
                  label="Day"
                  value={m.weekday}
                  onChange={(e) => update({ weekday: e.target.value })}
                >
                  {DAYS.map((d, k) => (
                    <option key={d} value={k}>
                      {d}
                    </option>
                  ))}
                </Select>
                <Input
                  label="Starts"
                  type="time"
                  value={m.start_time}
                  onChange={(e) => update({ start_time: e.target.value })}
                />
                <Input
                  label="Ends"
                  type="time"
                  value={m.end_time}
                  onChange={(e) => update({ end_time: e.target.value })}
                />
                <Input
                  label="Room"
                  value={m.location}
                  onChange={(e) => update({ location: e.target.value })}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMeetings(meetings.filter((_, j) => j !== i))}
                >
                  Remove
                </Button>
              </div>
            );
          })}
          {fields.meetings && (
            <p className="text-sm font-bold text-berry">Check the class times.</p>
          )}
          <Button
            variant="secondary"
            className="self-start"
            onClick={() =>
              setMeetings([
                ...meetings,
                { weekday: "0", start_time: "10:00", end_time: "11:15", location: "" },
              ])
            }
          >
            Add a class time
          </Button>
        </fieldset>
        <Button
          type="submit"
          className="self-start"
          pending={register.isPending}
          pendingLabel="Registering…"
          disabled={!form.code.trim() || !form.title.trim() || !form.teacher_email.trim()}
        >
          Register course
        </Button>
      </form>
      <section aria-labelledby="registered" className="flex flex-col gap-3">
        <h2 id="registered" className="text-lg font-bold">
          Registered courses
        </h2>
        <QueryView
          query={registrations}
          isEmpty={(d) => d.length === 0}
          empty={{ title: "No courses yet" }}
          skeleton={<SkeletonLines lines={4} />}
        >
          {(data) => (
            <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
              {data.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                  <span>
                    <span className="font-bold">{c.code}</span> {c.title}
                    <span className="block text-sm text-ink-soft">
                      {c.teacher_email} · {c.term}
                    </span>
                  </span>
                  <span
                    className={
                      c.claimed
                        ? "text-sm font-bold text-pine-strong"
                        : "text-sm font-bold text-ink-soft"
                    }
                  >
                    {c.claimed ? "Teacher signed up" : "Waiting for teacher"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </QueryView>
      </section>
    </div>
  );
}

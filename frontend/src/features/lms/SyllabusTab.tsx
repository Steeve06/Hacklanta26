import { Link } from "react-router-dom";
import { QueryView, SkeletonLines } from "@/components/ui";
import { formatShortDay, useTimezone } from "@/lib/time";
import { useSyllabus } from "./api";
import { useNumericParam } from "./useIds";
import { percent } from "@/lib/percent";

export function SyllabusTab() {
  const courseId = useNumericParam("courseId");
  const syllabus = useSyllabus(courseId);
  const tz = useTimezone();
  return (
    <QueryView query={syllabus} skeleton={<SkeletonLines lines={10} />}>
      {(data) => (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="flex flex-col gap-6">
            <section aria-labelledby="about">
              <h2 id="about" className="mb-2 text-lg font-bold">
                About this course
              </h2>
              <p className="max-w-prose">{data.description}</p>
            </section>
            <section aria-labelledby="schedule">
              <h2 id="schedule" className="mb-2 text-lg font-bold">
                Weekly schedule
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[28rem] text-left text-sm">
                  <thead>
                    <tr className="border-b border-line text-ink-soft">
                      <th scope="col" className="py-2 pr-3 font-bold">
                        Week
                      </th>
                      <th scope="col" className="py-2 pr-3 font-bold">
                        Starts
                      </th>
                      <th scope="col" className="py-2 pr-3 font-bold">
                        Topic
                      </th>
                      <th scope="col" className="py-2 font-bold">
                        Reading
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.weeks.map((week) => (
                      <tr key={week.week_number} className="border-b border-line align-top">
                        <td className="py-2 pr-3 font-bold">{week.week_number}</td>
                        <td className="whitespace-nowrap py-2 pr-3">
                          {formatShortDay(`${week.start_date}T12:00:00Z`, tz)}
                        </td>
                        <td className="py-2 pr-3">{week.topic}</td>
                        <td className="py-2">
                          {week.chapters.length === 0
                            ? "—"
                            : week.chapters.map((c) => (
                                <Link
                                  key={c.id}
                                  to={`/lms/courses/${courseId}/chapters/${c.id}`}
                                  className="block text-pine underline"
                                >
                                  Ch {c.order}
                                </Link>
                              ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section aria-labelledby="policies" className="flex max-w-prose flex-col gap-3">
              <h2 id="policies" className="text-lg font-bold">
                Policies
              </h2>
              <div>
                <h3 className="font-bold">Late work</h3>
                <p>{data.policies.late_work}</p>
              </div>
              <div>
                <h3 className="font-bold">Academic integrity</h3>
                <p>{data.policies.academic_integrity}</p>
              </div>
            </section>
          </div>
          <aside className="flex flex-col gap-6">
            <section
              aria-labelledby="instructor"
              className="rounded-lg border border-line bg-surface p-4"
            >
              <h2 id="instructor" className="mb-1 text-base font-bold">
                Instructor
              </h2>
              <p>{data.instructor_name}</p>
              <a href={`mailto:${data.instructor_email}`} className="text-sm text-pine underline">
                {data.instructor_email}
              </a>
              <h3 className="mt-3 text-sm font-bold">Office hours</h3>
              <p className="text-sm">{data.office_hours}</p>
            </section>
            <section
              aria-labelledby="grading"
              className="rounded-lg border border-line bg-surface p-4"
            >
              <h2 id="grading" className="mb-2 text-base font-bold">
                Grading
              </h2>
              <dl className="flex flex-col gap-2 text-sm">
                {data.grading.map((g) => (
                  <div key={g.label} className="flex flex-col gap-1">
                    <div className="flex justify-between">
                      <dt>{g.label}</dt>
                      <dd className="font-bold">{percent(g.weight_pct)}</dd>
                    </div>
                    <div className="h-1.5 rounded-full bg-sunken" aria-hidden="true">
                      <div
                        className="h-full rounded-full bg-ink-faint"
                        style={{ width: `${g.weight_pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </dl>
            </section>
          </aside>
        </div>
      )}
    </QueryView>
  );
}

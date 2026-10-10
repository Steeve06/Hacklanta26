import DOMPurify from "dompurify";
import { Link } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { Icon } from "@/components/Icon";
import { Button, QueryView, SkeletonLines, Skeleton, toast } from "@/components/ui";
import { useMe } from "@/features/auth/hooks";
import { formatShortDay, useTimezone } from "@/lib/time";
import { useChapter, useCompleteChapter, useCourse } from "./api";
import { useNumericParam } from "./useIds";

export function ChapterPage() {
  const courseId = useNumericParam("courseId");
  const chapterId = useNumericParam("chapterId");
  const course = useCourse(courseId);
  const chapter = useChapter(chapterId);
  const complete = useCompleteChapter(courseId);
  const me = useMe();
  const tz = useTimezone();
  const isStudent = me.data?.role === "student";

  return (
    <article className="flex flex-col gap-4">
      <Breadcrumbs
        items={[
          { label: "Courses", to: "/lms" },
          { label: course.data?.code ?? "Course", to: `/lms/courses/${courseId}` },
          { label: "Content", to: `/lms/courses/${courseId}` },
          { label: chapter.data ? `Chapter ${chapter.data.order}` : "Chapter" },
        ]}
      />
      <QueryView
        query={chapter}
        skeleton={
          <div className="flex flex-col gap-4">
            <Skeleton className="h-9 w-3/4" />
            <SkeletonLines lines={8} />
          </div>
        }
      >
        {(data) => (
          <>
            <header className="flex flex-col gap-2">
              <p className="text-sm font-bold text-ink-soft">
                {data.course_code} · Chapter {data.order} · {data.reading_minutes} min read
              </p>
              <h1 className="text-2xl font-bold md:text-3xl">{data.title}</h1>
              {!isStudent && (
                <Link
                  to={`/lms/courses/${courseId}/chapters/${chapterId}/edit`}
                  className="self-start text-sm font-bold text-pine underline"
                >
                  Edit chapter
                </Link>
              )}
            </header>
            {data.locked && isStudent ? (
              <p className="flex items-center gap-2 rounded-md border border-line bg-sunken p-4">
                <Icon name="lock" /> This chapter unlocks {formatShortDay(data.available_from, tz)}.
              </p>
            ) : (
              <>
                <section
                  aria-labelledby="objectives"
                  className="rounded-md border-l-4 border-pine bg-pine-soft/60 px-4 py-3"
                >
                  <h2 id="objectives" className="mb-1 text-base font-bold">
                    By the end you should be able to
                  </h2>
                  <ul className="list-disc pl-5 text-sm">
                    {data.objectives.map((o) => (
                      <li key={o}>{o}</li>
                    ))}
                  </ul>
                </section>
                <div
                  className="prose-chapter"
                  dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(data.body_html) }}
                />
                {data.links.length > 0 && (
                  <section aria-labelledby="links" className="max-w-prose">
                    <h2 id="links" className="mb-2 text-lg font-bold">
                      Further reading
                    </h2>
                    <ul className="list-disc pl-5">
                      {data.links.map((link) => (
                        <li key={link.url}>
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-pine underline"
                          >
                            {link.label}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                {isStudent && (
                  <footer className="flex max-w-prose flex-wrap items-center gap-3 border-t border-line pt-4">
                    {data.completed_at ? (
                      <p className="flex items-center gap-2 font-bold text-pine-strong">
                        <Icon name="check" /> Completed
                      </p>
                    ) : (
                      <Button
                        pending={complete.isPending}
                        pendingLabel="Saving…"
                        onClick={() =>
                          complete.mutate(chapterId, {
                            onError: (error) => toast.error(errorMessage(error)),
                          })
                        }
                      >
                        Mark chapter complete
                      </Button>
                    )}
                    <Link
                      to={`/lms/courses/${courseId}`}
                      className="inline-flex min-h-11 items-center font-bold text-ink-soft underline"
                    >
                      Back to chapters
                    </Link>
                  </footer>
                )}
              </>
            )}
          </>
        )}
      </QueryView>
    </article>
  );
}

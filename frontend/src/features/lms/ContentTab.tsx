import { Link } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { QueryView, Skeleton } from "@/components/ui";
import { useMe } from "@/features/auth/hooks";
import { formatShortDay, useTimezone } from "@/lib/time";
import { cx } from "@/lib/cx";
import { useChapters } from "./api";
import { useNumericParam } from "./useIds";

export function ContentTab() {
  const courseId = useNumericParam("courseId");
  const chapters = useChapters(courseId);
  const tz = useTimezone();
  const me = useMe();
  const isTeacher = me.data?.role !== "student";
  return (
    <section aria-labelledby="content-heading" className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 id="content-heading" className="text-lg font-bold">
          Chapters
        </h2>
        {isTeacher && (
          <Link
            to={`/lms/courses/${courseId}/chapters/new`}
            className="inline-flex min-h-11 items-center rounded-md bg-pine px-4 font-bold text-on-pine"
          >
            New chapter
          </Link>
        )}
      </div>
      <QueryView
        query={chapters}
        isEmpty={(d) => d.length === 0}
        empty={{
          title: "No chapters yet",
          body: "Chapters appear here when the instructor publishes them.",
        }}
        skeleton={
          <div className="flex flex-col gap-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        }
      >
        {(data) => (
          <ol className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
            {data.map((chapter) => {
              const locked = chapter.locked && !isTeacher;
              const body = (
                <>
                  <span
                    className={cx(
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 font-display font-bold",
                      chapter.completed_at
                        ? "border-pine bg-pine text-on-pine"
                        : "border-line text-ink-soft",
                    )}
                    aria-hidden="true"
                  >
                    {chapter.completed_at ? (
                      <Icon name="check" className="h-4 w-4" />
                    ) : (
                      chapter.order
                    )}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-bold">
                      Chapter {chapter.order}: {chapter.title}
                    </span>
                    <span className="text-sm text-ink-soft">
                      {chapter.locked
                        ? `Unlocks ${formatShortDay(chapter.available_from, tz)}`
                        : `${chapter.reading_minutes} min read${chapter.completed_at ? " · Completed" : chapter.opened_at ? " · Started" : ""}`}
                    </span>
                  </span>
                  {chapter.locked ? (
                    <Icon name="lock" className="h-5 w-5 text-ink-faint" label="Locked" />
                  ) : (
                    <Icon name="chevron" className="h-5 w-5 text-ink-faint" />
                  )}
                </>
              );
              return (
                <li key={chapter.id}>
                  {locked ? (
                    <div className="flex min-h-16 items-center gap-3 px-4 py-3 opacity-70">
                      {body}
                    </div>
                  ) : (
                    <Link
                      to={`/lms/courses/${courseId}/chapters/${chapter.id}`}
                      className="flex min-h-16 items-center gap-3 px-4 py-3 hover:bg-sunken"
                    >
                      {body}
                    </Link>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </QueryView>
    </section>
  );
}

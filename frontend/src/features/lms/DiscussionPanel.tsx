import { useState, type FormEvent } from "react";
import { errorMessage } from "@/api/client";
import { Icon } from "@/components/Icon";
import { Button, QueryView, Skeleton, Textarea, toast } from "@/components/ui";
import { formatExact, useTimezone } from "@/lib/time";
import { cx } from "@/lib/cx";
import { useNow } from "@/lib/useNow";
import { useDiscussion, usePostToDiscussion, type AssessmentDetail, type Discussion } from "./api";

type Post = Discussion["posts"][number];

export function DiscussionPanel({
  assessment,
  canPost,
}: {
  assessment: AssessmentDetail;
  canPost: boolean;
}) {
  const discussion = useDiscussion(assessment.id);
  const now = useNow();
  const closed =
    now > new Date(assessment.effective_cutoff_at ?? assessment.effective_due_at).getTime();
  return (
    <section
      aria-labelledby="discussion-heading"
      className="flex max-w-prose flex-col gap-4 border-t border-line pt-4"
    >
      <h2 id="discussion-heading" className="text-lg font-bold">
        Discussion
      </h2>
      <QueryView
        query={discussion}
        skeleton={
          <div className="flex flex-col gap-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        }
      >
        {(data) => (
          <>
            {data.progress && (
              <ul
                className="flex flex-col gap-1 rounded-md border border-line bg-surface p-3 text-sm"
                aria-label="Your progress"
              >
                <Requirement met={data.progress.original_posted} text="Original post" />
                <Requirement
                  met={data.progress.replies_made >= data.progress.replies_required}
                  text={`Replies to classmates: ${Math.min(data.progress.replies_made, data.progress.replies_required)} of ${data.progress.replies_required}`}
                />
              </ul>
            )}
            {canPost && !closed && !data.progress?.original_posted && (
              <Composer assessment={assessment} label="Your original post" submitLabel="Post" />
            )}
            {closed && <p className="text-sm text-ink-soft">This discussion is closed.</p>}
            <Thread posts={data.posts} assessment={assessment} canReply={canPost && !closed} />
          </>
        )}
      </QueryView>
    </section>
  );
}

function Requirement({ met, text }: { met: boolean; text: string }) {
  return (
    <li
      className={cx(
        "flex items-center gap-2",
        met ? "font-bold text-pine-strong" : "text-ink-soft",
      )}
    >
      <span
        aria-hidden="true"
        className={cx(
          "flex h-5 w-5 items-center justify-center rounded-full border",
          met ? "border-pine bg-pine text-on-pine" : "border-line",
        )}
      >
        {met && <Icon name="check" className="h-3 w-3" />}
      </span>
      {text}
      <span className="sr-only">{met ? "(done)" : "(not done yet)"}</span>
    </li>
  );
}

function Thread({
  posts,
  assessment,
  canReply,
}: {
  posts: Post[];
  assessment: AssessmentDetail;
  canReply: boolean;
}) {
  const roots = posts.filter((p) => p.parent === null);
  if (roots.length === 0)
    return <p className="text-sm text-ink-soft">No posts yet. Be the first.</p>;
  return (
    <ol className="flex flex-col gap-4">
      {roots.map((root) => (
        <li key={root.id}>
          <PostView post={root} assessment={assessment} canReply={canReply} />
          <ol className="ml-4 mt-2 flex flex-col gap-2 border-l-2 border-line pl-4">
            {posts
              .filter((p) => p.parent === root.id)
              .map((reply) => (
                <li key={reply.id}>
                  <PostView post={reply} assessment={assessment} canReply={false} />
                </li>
              ))}
          </ol>
        </li>
      ))}
    </ol>
  );
}

function PostView({
  post,
  assessment,
  canReply,
}: {
  post: Post;
  assessment: AssessmentDetail;
  canReply: boolean;
}) {
  const tz = useTimezone();
  const [replying, setReplying] = useState(false);
  return (
    <article
      className={cx(
        "rounded-md border p-3",
        post.is_mine ? "border-pine/40 bg-pine-soft/40" : "border-line bg-surface",
      )}
    >
      <header className="mb-1 flex flex-wrap items-baseline gap-2 text-sm">
        <span className="font-bold">{post.is_mine ? "You" : post.author_name}</span>
        <time dateTime={post.created_at} className="text-ink-soft">
          {formatExact(post.created_at, tz)}
        </time>
      </header>
      <p className="whitespace-pre-line">{post.body}</p>
      {canReply && !post.is_mine && !replying && (
        <button
          type="button"
          onClick={() => setReplying(true)}
          className="mt-1 min-h-11 text-sm font-bold text-pine underline"
        >
          Reply
        </button>
      )}
      {replying && (
        <div className="mt-2">
          <Composer
            assessment={assessment}
            parent={post.id}
            label={`Reply to ${post.author_name}`}
            submitLabel="Post reply"
            onDone={() => setReplying(false)}
          />
        </div>
      )}
    </article>
  );
}

function Composer({
  assessment,
  parent,
  label,
  submitLabel,
  onDone,
}: {
  assessment: AssessmentDetail;
  parent?: number;
  label: string;
  submitLabel: string;
  onDone?: () => void;
}) {
  const [body, setBody] = useState("");
  const [touched, setTouched] = useState(false);
  const post = usePostToDiscussion(assessment);
  const error = touched && !body.trim() ? "Write something before posting." : undefined;

  function submit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!body.trim()) return;
    post.mutate(
      { body, parent: parent ?? null },
      {
        onSuccess: () => {
          setBody("");
          setTouched(false);
          toast.success("Posted.");
          onDone?.();
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  return (
    <form noValidate onSubmit={submit} className="flex flex-col gap-2">
      <Textarea
        label={label}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onBlur={() => setTouched(true)}
        error={error}
        disabled={post.isPending}
      />
      <div className="flex gap-2">
        <Button type="submit" size="sm" pending={post.isPending} pendingLabel="Posting…">
          {submitLabel}
        </Button>
        {onDone && (
          <Button variant="ghost" size="sm" onClick={onDone} disabled={post.isPending}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

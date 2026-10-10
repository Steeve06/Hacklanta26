import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { errorMessage } from "@/api/client";
import { Icon } from "@/components/Icon";
import { Button, ErrorState, Spinner } from "@/components/ui";
import { cx } from "@/lib/cx";
import { useDelayed } from "@/lib/useDelayed";
import {
  isWaiting,
  useConfirmChanges,
  useConversation,
  useDeclineChanges,
  useSendMessage,
  useStartOver,
  type ChatMessage,
} from "./api";

const EXAMPLES = ["Skip my next session", "I'm busy Friday evening", "Keep Sundays free"];

export function AssistantPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={onClose}
      aria-labelledby="assistant-title"
      className="fixed inset-0 m-0 ml-auto h-dvh max-h-none w-full max-w-none border-l border-line bg-surface p-0 text-ink backdrop:bg-ink/30 md:w-[26rem]"
    >
      {open && <Chat onClose={onClose} />}
    </dialog>
  );
}

function Chat({ onClose }: { onClose: () => void }) {
  const conversation = useConversation(true);
  const startOver = useStartOver();
  const messages = conversation.data?.messages ?? [];

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-2">
        <h2 id="assistant-title" className="font-display text-lg font-bold">
          Ask Pulse
        </h2>
        <div className="flex items-center gap-1">
          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => startOver.mutate()}
              pending={startOver.isPending}
              pendingLabel="Clearing…"
              disabled={isWaiting(conversation.data)}
            >
              Start over
            </Button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-ink-soft hover:bg-sunken hover:text-ink"
          >
            <Icon name="close" label="Close" />
          </button>
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {conversation.isError ? (
          <ErrorState
            message={errorMessage(conversation.error)}
            onRetry={() => void conversation.refetch()}
            retrying={conversation.isFetching}
          />
        ) : conversation.isPending ? (
          <LoadingLine label="Loading your conversation…" />
        ) : (
          <Messages messages={messages} />
        )}
      </div>
      <Composer
        disabled={conversation.isPending || isWaiting(conversation.data)}
        empty={messages.length === 0 && !conversation.isPending}
      />
    </div>
  );
}

function LoadingLine({ label }: { label: string }) {
  const visible = useDelayed(true);
  if (!visible) return null;
  return (
    <p className="flex items-center gap-2 text-sm text-ink-soft">
      <Spinner className="h-4 w-4" />
      {label}
    </p>
  );
}

function Messages({ messages }: { messages: ChatMessage[] }) {
  const end = useRef<HTMLDivElement>(null);
  const last = messages.at(-1);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, last?.state, last?.proposal]);

  if (messages.length === 0)
    return (
      <div className="flex flex-col gap-2 text-sm text-ink-soft">
        <p>
          Tell me what should change: a session to skip or move, a time you're busy, or how much you
          want to study.
        </p>
        <p>I'll suggest the change, and nothing happens until you confirm it.</p>
      </div>
    );
  return (
    <div role="log" aria-live="polite" aria-label="Conversation" className="flex flex-col gap-3">
      {messages.map((m) =>
        m.role === "student" ? (
          <p
            key={m.id}
            className="ml-8 self-end whitespace-pre-wrap rounded-lg bg-pine-soft px-3 py-2 text-ink"
          >
            <span className="sr-only">You: </span>
            {m.text}
          </p>
        ) : (
          <Reply key={m.id} message={m} />
        ),
      )}
      <div ref={end} />
    </div>
  );
}

function Reply({ message }: { message: ChatMessage }) {
  if (message.state === "pending") return <LoadingLine label="Thinking…" />;
  return (
    <div className="mr-8 flex flex-col gap-2">
      <p className={cx("whitespace-pre-wrap", message.state === "failed" && "text-ink-soft")}>
        <span className="sr-only">Pulse: </span>
        {message.text}
      </p>
      {message.changes.length > 0 && <Proposal message={message} />}
    </div>
  );
}

function Proposal({ message }: { message: ChatMessage }) {
  const confirm = useConfirmChanges();
  const decline = useDeclineChanges();
  const busy = confirm.isPending || decline.isPending;
  const error = confirm.error ?? decline.error;
  return (
    <section
      aria-label="Suggested changes"
      className={cx(
        "rounded-lg border p-3",
        message.proposal === "pending" ? "border-pine bg-surface" : "border-line bg-sunken",
      )}
    >
      <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
        {message.changes.map((c, i) => (
          <li key={i}>{c.summary}</li>
        ))}
      </ul>
      {message.proposal === "pending" && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            size="sm"
            onClick={() => confirm.mutate(message.id)}
            pending={confirm.isPending}
            pendingLabel="Applying…"
            disabled={busy}
          >
            Confirm
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => decline.mutate(message.id)}
            disabled={busy}
          >
            Not now
          </Button>
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm font-bold text-berry">
          {errorMessage(error)}
        </p>
      )}
      <ProposalOutcome message={message} />
    </section>
  );
}

function ProposalOutcome({ message }: { message: ChatMessage }) {
  if (message.proposal === "applied")
    return (
      <p className="mt-2 flex items-center gap-1 text-sm font-bold text-pine-strong">
        <Icon name="check" className="h-4 w-4" />
        Applied. Your schedule updates in a few seconds.
      </p>
    );
  if (message.proposal === "declined")
    return <p className="mt-2 text-sm text-ink-soft">{message.proposal_note || "Not applied."}</p>;
  if (message.proposal === "failed")
    return (
      <p className="mt-2 text-sm font-bold text-berry">
        Couldn't apply this: {message.proposal_note}
      </p>
    );
  return null;
}

function Composer({ disabled, empty }: { disabled: boolean; empty: boolean }) {
  const [text, setText] = useState("");
  const send = useSendMessage();
  const input = useRef<HTMLTextAreaElement>(null);
  const trimmed = text.trim();
  const blocked = disabled || send.isPending;

  useEffect(() => {
    input.current?.focus();
  }, []);

  const submit = (value: string) => {
    if (!value.trim() || blocked) return;
    send.mutate(value.trim(), { onSuccess: () => setText("") });
  };
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit(text);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit(text);
    }
  };

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-2 border-t border-line px-4 py-3">
      {empty && (
        <div className="flex flex-wrap gap-2" aria-label="Examples">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => submit(example)}
              disabled={blocked}
              className="min-h-11 rounded-full border border-line px-3 text-sm text-ink-soft hover:border-ink-faint hover:text-ink disabled:opacity-60 md:min-h-9"
            >
              {example}
            </button>
          ))}
        </div>
      )}
      {send.isError && (
        <p role="alert" className="text-sm font-bold text-berry">
          {errorMessage(send.error)}
        </p>
      )}
      <div className="flex items-end gap-2">
        <label htmlFor="assistant-input" className="sr-only">
          Message
        </label>
        <textarea
          id="assistant-input"
          ref={input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          maxLength={1000}
          placeholder="What should change?"
          className="min-h-11 flex-1 resize-none rounded-md border border-line bg-surface px-3 py-2 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink"
        />
        <Button type="submit" disabled={!trimmed || blocked} pending={send.isPending}>
          Send
        </Button>
      </div>
    </form>
  );
}

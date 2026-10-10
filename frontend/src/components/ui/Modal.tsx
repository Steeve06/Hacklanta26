import { useEffect, useRef, type ReactNode } from "react";

type Props = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
};

export function Modal({ open, title, onClose, children, footer }: Props) {
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
      aria-labelledby="modal-title"
      className="w-[min(32rem,calc(100vw-2rem))] rounded-lg border border-line bg-surface p-0 text-ink backdrop:bg-ink/40"
    >
      <div className="flex flex-col gap-4 p-5">
        <h2 id="modal-title" className="text-xl font-bold">
          {title}
        </h2>
        <div>{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2">{footer}</div>}
      </div>
    </dialog>
  );
}

export function ConfirmModal({
  open,
  title,
  body,
  confirmLabel,
  onConfirm,
  onClose,
  pending,
}: {
  open: boolean;
  title: string;
  body: string;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  pending?: boolean;
}) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      footer={
        <>
          <button
            type="button"
            className="min-h-11 rounded-md px-4 font-bold text-ink-soft hover:bg-sunken"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={pending}
            className="min-h-11 rounded-md bg-berry px-4 font-bold text-white disabled:opacity-60"
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      <p className="text-ink-soft">{body}</p>
    </Modal>
  );
}

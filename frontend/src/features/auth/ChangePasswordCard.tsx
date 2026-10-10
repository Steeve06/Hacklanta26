import { useId, useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "@/api/client";
import { Button, Card, toast } from "@/components/ui";
import { useChangePassword, useMe } from "./hooks";
import { PasswordInput } from "./PasswordInput";
import { PasswordRules } from "./PasswordRules";
import { passwordProblem, passwordRules } from "./passwordRules";

const EMPTY = { current_password: "", new_password: "", new_password_confirm: "" };

export function ChangePasswordCard() {
  const me = useMe();
  const change = useChangePassword();
  const rulesId = useId();
  const [form, setForm] = useState(EMPTY);
  const [touched, setTouched] = useState(false);
  const rules = passwordRules(form.new_password, me.data?.email ?? "", [
    me.data?.first_name ?? "",
    me.data?.last_name ?? "",
  ]);
  const server = change.error instanceof ApiError ? change.error.fields : {};
  const local = {
    current_password: form.current_password ? undefined : "Enter your current password.",
    new_password: passwordProblem(rules),
    new_password_confirm:
      form.new_password_confirm === form.new_password ? undefined : "Passwords don't match.",
  };
  const invalid = Object.values(local).some(Boolean);
  const errorFor = (name: keyof typeof local) =>
    (touched ? local[name] : undefined) ?? server[name]?.[0];

  function submit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (invalid || change.isPending) return;
    change.mutate(form, {
      onSuccess: (data) => {
        toast.success(data.detail);
        setForm(EMPTY);
        setTouched(false);
      },
    });
  }

  const set = (name: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [name]: e.target.value }));

  return (
    <Card aria-labelledby="password-heading">
      <h2 id="password-heading" className="mb-1 text-lg font-bold">
        Password
      </h2>
      <p className="mb-3 text-sm text-ink-soft">Changing it signs you out on every other device.</p>
      <form noValidate onSubmit={submit} className="flex max-w-md flex-col gap-3">
        <PasswordInput
          label="Current password"
          autoComplete="current-password"
          value={form.current_password}
          onChange={set("current_password")}
          error={errorFor("current_password")}
          disabled={change.isPending}
        />
        <PasswordInput
          label="New password"
          autoComplete="new-password"
          value={form.new_password}
          onChange={set("new_password")}
          error={errorFor("new_password")}
          describedBy={rulesId}
          disabled={change.isPending}
        />
        {form.new_password && <PasswordRules id={rulesId} rules={rules} />}
        <PasswordInput
          label="Confirm new password"
          autoComplete="new-password"
          value={form.new_password_confirm}
          onChange={set("new_password_confirm")}
          error={errorFor("new_password_confirm")}
          disabled={change.isPending}
        />
        {change.isError && !Object.keys(server).some((k) => k in EMPTY) && (
          <p role="alert" className="text-sm font-bold text-berry">
            {errorMessage(change.error)}
          </p>
        )}
        <Button
          type="submit"
          className="self-start"
          pending={change.isPending}
          pendingLabel="Saving…"
        >
          Change password
        </Button>
      </form>
    </Card>
  );
}

import { useId, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, errorMessage } from "@/api/client";
import { Button } from "@/components/ui";
import { AuthLayout } from "./AuthLayout";
import { useConfirmReset } from "./hooks";
import { PasswordInput } from "./PasswordInput";
import { PasswordRules } from "./PasswordRules";
import { passwordProblem, passwordRules } from "./passwordChecks";

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const uid = params.get("uid") ?? "";
  const token = params.get("token") ?? "";
  const confirm = useConfirmReset();
  const rulesId = useId();
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [touched, setTouched] = useState({ password: false, again: false });
  const rules = passwordRules(password, "");
  const server = confirm.error instanceof ApiError ? confirm.error.fields : {};
  const passwordError =
    (touched.password ? passwordProblem(rules) : undefined) ?? server.password?.[0];
  const againError = touched.again && again !== password ? "Passwords don't match." : undefined;
  const invalid = Boolean(passwordProblem(rules)) || again !== password;

  if (!uid || !token) {
    return (
      <AuthLayout title="Reset your password">
        <p className="mb-3">This link is incomplete. Ask for a new one.</p>
        <Link to="/forgot-password" className="font-bold text-pine underline">
          Send a new link
        </Link>
      </AuthLayout>
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setTouched({ password: true, again: true });
    if (invalid || confirm.isPending) return;
    confirm.mutate({ uid, token, password, password_confirm: again });
  }

  if (confirm.isSuccess) {
    return (
      <AuthLayout title="Password changed">
        <div role="status" className="flex flex-col gap-3">
          <p>{confirm.data.detail}</p>
          <p className="text-sm text-ink-soft">For safety, every device was signed out.</p>
          <Link to="/login" className="font-bold text-pine underline">
            Sign in
          </Link>
        </div>
      </AuthLayout>
    );
  }

  const linkProblem = confirm.isError && !server.password ? errorMessage(confirm.error) : undefined;

  return (
    <AuthLayout title="Choose a new password" busy={confirm.isPending}>
      <form noValidate onSubmit={submit} className="flex flex-col gap-4">
        <PasswordInput
          label="New password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onBlur={() => setTouched((t) => ({ ...t, password: true }))}
          error={passwordError}
          describedBy={rulesId}
          disabled={confirm.isPending}
        />
        <PasswordRules id={rulesId} rules={rules.filter((r) => r.id !== "personal")} />
        <PasswordInput
          label="Confirm new password"
          autoComplete="new-password"
          value={again}
          onChange={(e) => setAgain(e.target.value)}
          onBlur={() => setTouched((t) => ({ ...t, again: true }))}
          error={againError}
          disabled={confirm.isPending}
        />
        {linkProblem && (
          <div role="alert" className="flex flex-col gap-2 text-sm">
            <p className="font-bold text-berry">{linkProblem}</p>
            <Link to="/forgot-password" className="font-bold text-pine underline">
              Send a new link
            </Link>
          </div>
        )}
        <Button type="submit" pending={confirm.isPending} pendingLabel="Saving…">
          Save new password
        </Button>
      </form>
    </AuthLayout>
  );
}

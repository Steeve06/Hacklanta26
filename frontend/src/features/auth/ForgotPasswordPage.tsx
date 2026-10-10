import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Button, Input } from "@/components/ui";
import { AuthLayout } from "./AuthLayout";
import { useRequestReset } from "./hooks";

const EMAIL = /^\S+@\S+\.\S+$/;

export function ForgotPasswordPage() {
  const request = useRequestReset();
  const [email, setEmail] = useState("");
  const [touched, setTouched] = useState(false);
  const error = touched && !EMAIL.test(email.trim()) ? "Enter a valid email address." : undefined;

  function submit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!EMAIL.test(email.trim()) || request.isPending) return;
    request.mutate(email.trim());
  }

  return (
    <AuthLayout title="Reset your password" busy={request.isPending}>
      {request.isSuccess ? (
        <div className="flex flex-col gap-3" role="status">
          <p>{request.data.detail}</p>
          <p className="text-sm text-ink-soft">
            The link works once and expires in an hour. Check your spam folder if it doesn't arrive.
          </p>
          <Link to="/login" className="font-bold text-pine underline">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form noValidate onSubmit={submit} className="flex flex-col gap-4">
          <p className="text-sm text-ink-soft">
            Enter the email you signed up with and we'll send you a link to choose a new password.
          </p>
          <Input
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={() => setTouched(true)}
            error={error}
            disabled={request.isPending}
          />
          {request.isError && (
            <p role="alert" className="text-sm font-bold text-berry">
              {errorMessage(request.error)}
            </p>
          )}
          <Button type="submit" pending={request.isPending} pendingLabel="Sending…">
            Send reset link
          </Button>
          <Link to="/login" className="text-sm font-bold text-pine underline">
            Back to sign in
          </Link>
        </form>
      )}
    </AuthLayout>
  );
}

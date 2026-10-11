import { useId, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, errorMessage, isUnreachable } from "@/api/client";
import { Button, ChipGroup, Input } from "@/components/ui";
import { AuthLayout } from "./AuthLayout";
import { useSignup } from "./hooks";
import { PasswordInput } from "./PasswordInput";
import { PasswordRules } from "./PasswordRules";
import { passwordProblem, passwordRules } from "./passwordChecks";
import { homeFor } from "./redirects";

const EMAIL = /^\S+@\S+\.\S+$/;
type FieldName = "first_name" | "last_name" | "email" | "password" | "password_confirm";

function browserTimezone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

export function SignupPage() {
  const navigate = useNavigate();
  const signup = useSignup();
  const rulesId = useId();
  const [role, setRole] = useState<"student" | "teacher">("student");
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    password_confirm: "",
  });
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>({});
  const rules = passwordRules(form.password, form.email, [form.first_name, form.last_name]);

  const local: Partial<Record<FieldName, string>> = {
    first_name: form.first_name.trim() ? undefined : "Enter your first name.",
    last_name: form.last_name.trim() ? undefined : "Enter your last name.",
    email: EMAIL.test(form.email.trim()) ? undefined : "Enter a valid email address.",
    password: passwordProblem(rules),
    password_confirm:
      form.password_confirm && form.password_confirm === form.password
        ? undefined
        : "Passwords don't match.",
  };
  const server = signup.error instanceof ApiError ? signup.error.fields : {};
  const errorFor = (name: FieldName) =>
    (touched[name] ? local[name] : undefined) ?? server[name]?.[0];
  const invalid = Object.values(local).some(Boolean);

  const set = (name: FieldName) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((f) => ({ ...f, [name]: e.target.value }));
    if (signup.isError) signup.reset();
  };
  const blur = (name: FieldName) => () => setTouched((t) => ({ ...t, [name]: true }));

  function submit(event?: FormEvent) {
    event?.preventDefault();
    setTouched({
      first_name: true,
      last_name: true,
      email: true,
      password: true,
      password_confirm: true,
    });
    if (invalid || signup.isPending) return;
    signup.mutate(
      { ...form, role, email: form.email.trim(), timezone: browserTimezone() },
      { onSuccess: (me) => navigate(homeFor(me), { replace: true }) },
    );
  }

  const general =
    signup.isError && !Object.keys(server).some((k) => k in form)
      ? errorMessage(signup.error)
      : undefined;

  return (
    <AuthLayout title="Create your account" busy={signup.isPending || signup.isSuccess}>
      <form noValidate onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <ChipGroup<"student" | "teacher">
            label="I am"
            value={role}
            onChange={(next) => {
              setRole(next);
              if (signup.isError) signup.reset();
            }}
            options={[
              { value: "student", label: "I'm a student" },
              { value: "teacher", label: "I teach a course" },
            ]}
          />
          {role === "teacher" && (
            <p className="text-sm text-ink-soft">
              Use the email your department registered your course with. Your course is waiting for
              you; you only add the content.
            </p>
          )}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="First name"
            autoComplete="given-name"
            value={form.first_name}
            onChange={set("first_name")}
            onBlur={blur("first_name")}
            error={errorFor("first_name")}
            disabled={signup.isPending}
            maxLength={80}
          />
          <Input
            label="Last name"
            autoComplete="family-name"
            value={form.last_name}
            onChange={set("last_name")}
            onBlur={blur("last_name")}
            error={errorFor("last_name")}
            disabled={signup.isPending}
            maxLength={80}
          />
        </div>
        <Input
          label={role === "teacher" ? "School email" : "Email"}
          type="email"
          autoComplete="email"
          value={form.email}
          onChange={set("email")}
          onBlur={blur("email")}
          error={errorFor("email")}
          disabled={signup.isPending}
        />
        <PasswordInput
          label="Password"
          autoComplete="new-password"
          value={form.password}
          onChange={set("password")}
          onBlur={blur("password")}
          error={errorFor("password")}
          describedBy={rulesId}
          disabled={signup.isPending}
        />
        <PasswordRules id={rulesId} rules={rules} />
        <PasswordInput
          label="Confirm password"
          autoComplete="new-password"
          value={form.password_confirm}
          onChange={set("password_confirm")}
          onBlur={blur("password_confirm")}
          error={errorFor("password_confirm")}
          disabled={signup.isPending}
        />
        {general && (
          <div
            role="alert"
            className="flex flex-col items-start gap-2 text-sm font-bold text-berry"
          >
            <p>{general}</p>
            {isUnreachable(signup.error) && (
              <Button size="sm" variant="secondary" onClick={() => submit()}>
                Retry
              </Button>
            )}
          </div>
        )}
        <Button type="submit" pending={signup.isPending} pendingLabel="Creating your account…">
          Create account
        </Button>
      </form>
      <p className="mt-4 border-t border-line pt-4 text-sm">
        Already have an account?{" "}
        <Link to="/login" className="font-bold text-pine underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}

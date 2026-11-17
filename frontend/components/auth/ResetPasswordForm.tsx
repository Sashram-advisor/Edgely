"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import Field from "./Field";
import { ApiError, authApi } from "@/utilities/api";
import { PASSWORD_MIN_LENGTH, validateNewPassword } from "@/utilities/validation";

type Errors = { password?: string; confirm?: string };

export default function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!token) {
    return (
      <>
        <header className="auth-heading">
          <h1>This link isn’t valid</h1>
          <p>
            The reset link is missing or incomplete. Request a new one and use
            the link in the latest email.
          </p>
        </header>
        <Link className="submit submit-link" href="/forgot-password">
          Request a new link
        </Link>
      </>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");

    const nextErrors: Errors = {
      password: validateNewPassword(password),
      confirm: confirm === password ? undefined : "The passwords don’t match.",
    };
    setErrors(nextErrors);
    if (nextErrors.password || nextErrors.confirm) return;

    setSubmitting(true);
    try {
      await authApi.resetPassword({ token, password });
      router.push("/login?reset=1");
    } catch (error) {
      setFormError(
        error instanceof ApiError && (error.status === 400 || error.status === 410)
          ? "This reset link has expired or was already used. Request a new one."
          : error instanceof ApiError
            ? error.message
            : "Something went wrong. Please try again.",
      );
      setSubmitting(false);
    }
  }

  return (
    <>
      <header className="auth-heading">
        <h1>Choose a new password</h1>
        <p>You’ll use it the next time you log in.</p>
      </header>

      {formError && (
        <p className="notice notice-error" role="alert">
          {formError}{" "}
          <Link className="inline-link" href="/forgot-password">
            Request a new link
          </Link>
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <Field
          label="New password"
          name="password"
          type="password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          hint={`At least ${PASSWORD_MIN_LENGTH} characters, with a letter and a number.`}
          autoComplete="new-password"
          disabled={submitting}
          autoFocus
        />
        <Field
          label="Confirm new password"
          name="confirm"
          type="password"
          value={confirm}
          onChange={setConfirm}
          error={errors.confirm}
          autoComplete="new-password"
          disabled={submitting}
        />
        <button className="submit" type="submit" disabled={submitting}>
          {submitting ? "Saving…" : "Save new password"}
        </button>
      </form>
    </>
  );
}

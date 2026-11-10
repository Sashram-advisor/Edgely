"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";
import Field from "./Field";
import { ApiError, authApi } from "@/utilities/api";
import { validateEmail } from "@/utilities/validation";

export default function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | undefined>();
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sentTo, setSentTo] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");

    const emailError = validateEmail(email);
    setError(emailError);
    if (emailError) return;

    setSubmitting(true);
    try {
      await authApi.forgotPassword({ email: email.trim() });
      setSentTo(email.trim());
    } catch (err) {
      setFormError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (sentTo) {
    return (
      <>
        <header className="auth-heading">
          <h1>Check your email</h1>
          <p>
            If an account exists for <strong>{sentTo}</strong>, we’ve sent a link
            to reset your password. It may take a minute to arrive.
          </p>
        </header>
        <button
          className="submit submit-secondary"
          type="button"
          onClick={() => setSentTo("")}
        >
          Use a different email
        </button>
        <p className="switch-line">
          <Link href="/login">Back to log in</Link>
        </p>
      </>
    );
  }

  return (
    <>
      <header className="auth-heading">
        <h1>Reset your password</h1>
        <p>Enter your email and we’ll send you a link to choose a new password.</p>
      </header>

      {formError && (
        <p className="notice notice-error" role="alert">
          {formError}
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <Field
          label="Email"
          name="email"
          type="email"
          value={email}
          onChange={setEmail}
          error={error}
          autoComplete="email"
          disabled={submitting}
          autoFocus
        />
        <button className="submit" type="submit" disabled={submitting}>
          {submitting ? "Sending link…" : "Send reset link"}
        </button>
      </form>

      <p className="switch-line">
        Remembered it? <Link href="/login">Back to log in</Link>
      </p>
    </>
  );
}

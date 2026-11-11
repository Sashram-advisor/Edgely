"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import Field from "./Field";
import { ApiError, authApi } from "@/utilities/api";
import { validateEmail } from "@/utilities/validation";

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const justReset = searchParams.get("reset") === "1";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");

    const nextErrors = {
      email: validateEmail(email),
      password: password ? undefined : "Enter your password.",
    };
    setErrors(nextErrors);
    if (nextErrors.email || nextErrors.password) return;

    setSubmitting(true);
    try {
      await authApi.login({ email: email.trim(), password });
      router.push("/dashboard");
    } catch (error) {
      setFormError(
        error instanceof ApiError && error.status === 401
          ? "That email and password don’t match. Check them and try again."
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
        <h1>Welcome back</h1>
        <p>Log in to continue your study plan.</p>
      </header>

      {justReset && (
        <p className="notice notice-success" role="status">
          Your password was updated. Log in with your new password.
        </p>
      )}
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
          error={errors.email}
          autoComplete="email"
          disabled={submitting}
          autoFocus
        />
        <Field
          label="Password"
          name="password"
          type="password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          autoComplete="current-password"
          disabled={submitting}
          labelAction={
            <Link className="inline-link" href="/forgot-password">
              Forgot password?
            </Link>
          }
        />
        <button className="submit" type="submit" disabled={submitting}>
          {submitting ? "Logging in…" : "Log in"}
        </button>
      </form>

      <p className="switch-line">
        New to Edgely? <Link href="/register">Create an account</Link>
      </p>
    </>
  );
}

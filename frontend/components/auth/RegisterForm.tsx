"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import Field from "./Field";
import { ApiError, authApi } from "@/utilities/api";
import {
  PASSWORD_MIN_LENGTH,
  validateEmail,
  validateName,
  validateNewPassword,
} from "@/utilities/validation";

type Errors = { name?: string; email?: string; password?: string };

export default function RegisterForm() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");

    const nextErrors: Errors = {
      name: validateName(name),
      email: validateEmail(email),
      password: validateNewPassword(password),
    };
    setErrors(nextErrors);
    if (nextErrors.name || nextErrors.email || nextErrors.password) return;

    setSubmitting(true);
    try {
      await authApi.register({
        full_name: name.trim(),
        email: email.trim(),
        password,
      });
      router.push("/dashboard");
    } catch (error) {
      setFormError(
        error instanceof ApiError && error.status === 409
          ? "An account with this email already exists. Try logging in instead."
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
        <h1>Create your account</h1>
        <p>Set up your learning path in a few minutes.</p>
      </header>

      {formError && (
        <p className="notice notice-error" role="alert">
          {formError}
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <Field
          label="Full name"
          name="name"
          value={name}
          onChange={setName}
          error={errors.name}
          autoComplete="name"
          disabled={submitting}
          autoFocus
        />
        <Field
          label="Email"
          name="email"
          type="email"
          value={email}
          onChange={setEmail}
          error={errors.email}
          autoComplete="email"
          disabled={submitting}
        />
        <Field
          label="Password"
          name="password"
          type="password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          hint={`At least ${PASSWORD_MIN_LENGTH} characters, with a letter and a number.`}
          autoComplete="new-password"
          disabled={submitting}
        />
        <button className="submit" type="submit" disabled={submitting}>
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="switch-line">
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </>
  );
}

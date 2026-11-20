"use client";

// Auth actions that the form components call. These wrap the Supabase browser
// client and translate Supabase error messages into short, user-facing text.

import { supabase } from "./supabase";
import { ensurePlatformUser } from "./api";

export class AuthError extends Error {}

function friendlyMessage(error: { message?: string } | null): string {
  const message = error?.message ?? "";
  if (message.includes("Invalid login credentials")) {
    return "That email and password don’t match. Check them and try again.";
  }
  if (message.includes("already registered") || message.includes("already exists")) {
    return "An account with this email already exists. Try logging in instead.";
  }
  if (message.includes("Auth session missing")) {
    return "This reset link has expired or was already used. Request a new one.";
  }
  if (message.includes("Password should be")) {
    return "Your password is too short. Use at least 8 characters.";
  }
  return message || "Something went wrong. Please try again.";
}

export async function signIn(email: string, password: string): Promise<void> {
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new AuthError(friendlyMessage(error));
  // A4: create the platform user on first login. Idempotent — safe to call every time.
  await ensurePlatformUser();
}

export async function signUp(
  fullName: string,
  email: string,
  password: string,
): Promise<{ needsEmailConfirmation: boolean }> {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { data: { full_name: fullName } },
  });
  if (error) throw new AuthError(friendlyMessage(error));

  if (!data.session) {
    // Email confirmation is on: Supabase created the auth user but there is no
    // session yet, so we cannot call the backend. Provisioning happens on the
    // first real login instead.
    return { needsEmailConfirmation: true };
  }

  // A4: provision the platform user now that we have a session.
  await ensurePlatformUser(fullName);
  return { needsEmailConfirmation: false };
}

export async function signOut(): Promise<void> {
  await supabase.auth.signOut();
}

export async function sendPasswordResetEmail(email: string): Promise<void> {
  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/reset-password`,
  });
  if (error) throw new AuthError(friendlyMessage(error));
}

export async function resetPassword(password: string): Promise<void> {
  // The recovery link (…#access_token=…&type=recovery) is picked up by the
  // Supabase client automatically, establishing a session; updateUser then
  // changes the password for that session.
  const { error } = await supabase.auth.updateUser({ password });
  if (error) throw new AuthError(friendlyMessage(error));
  // The recovery session is no longer useful once the password has changed.
  await supabase.auth.signOut();
}

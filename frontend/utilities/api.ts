// Typed client for the Edgely FastAPI backend.
//
// Every request attaches the current Supabase access token as
// `Authorization: Bearer <token>` (A3). The backend verifies that token in
// core/auth_provider.py and never trusts a user id sent from the browser.

import { supabase } from "./supabase";
import type { UserProfile } from "@/types/auth";
import type { ChatDone } from "@/types/tutor";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// FastAPI returns { detail: "text" } or { detail: [{ msg: "text" }, ...] }.
function extractMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string };
      if (first?.msg) return first.msg;
    }
  }
  return fallback;
}

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(await authHeaders()),
        ...(init.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      "Can’t reach Edgely right now. Check your connection and try again.",
      0,
    );
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(
      extractMessage(data, "Something went wrong. Please try again."),
      response.status,
    );
  }
  return data as T;
}

export function getJson<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

// A4: POST /users/me provisions the platform user for the current login.
// The route is idempotent (upsert on external_auth_id), so calling it on every
// login is safe. `display_name` names a NEW user and is ignored on later calls.
export async function ensurePlatformUser(displayName?: string): Promise<UserProfile> {
  return postJson<UserProfile>(
    "/users/me",
    displayName ? { display_name: displayName } : {},
  );
}

export async function getMyProfile(): Promise<UserProfile> {
  return getJson<UserProfile>("/users/me");
}

// Non-streaming tutor call. The chat UI uses streamTutorChat (utilities/streaming.ts)
// for the live typing experience; this stays available for quick checks.
export async function tutorChat(body: {
  message: string;
  conversation_id?: number | null;
  certification_id?: number | null;
}): Promise<ChatDone> {
  return postJson<ChatDone>("/tutor/chat", body);
}

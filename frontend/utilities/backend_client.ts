// Authenticated client for the platform API (/users, /certifications,
// /enrollments, /tutor). Every request carries the Supabase access token as
// "Authorization: Bearer <token>", which is what backend/app/core/auth_provider.py reads.
//
// Where the token comes from is the sign-in chain's job (checklist A2/A3,
// utilities/authentication.ts). Once the Supabase client exists, register it once:
//
//     setAccessTokenProvider(async () =>
//       (await supabase.auth.getSession()).data.session?.access_token ?? null);
//
// Until then every call fails with 401 and the pages show a "please sign in" state.

import { ApiError } from "@/utilities/api";
import type {
  Certification,
  Enrollment,
  EnrollmentCreate,
  EnrollmentUpdate,
  LearnerContext,
  PlatformUser,
  UserUpdate,
} from "@/types/learning";

export { ApiError };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// The backend's 403 detail when the token is valid but POST /users/me never ran.
const NO_PLATFORM_USER = "No platform user exists for this login";

type TokenProvider = () => Promise<string | null> | string | null;

// Local development only: until sign-in exists, a Supabase access token pasted
// into frontend/.env.local as NEXT_PUBLIC_DEV_ACCESS_TOKEN lets the pages talk to
// a real backend. Ignored in production builds. Never commit a token.
const DEV_TOKEN =
  process.env.NODE_ENV !== "production" ? process.env.NEXT_PUBLIC_DEV_ACCESS_TOKEN || null : null;

let tokenProvider: TokenProvider = () => DEV_TOKEN;

export function setAccessTokenProvider(provider: TokenProvider): void {
  tokenProvider = provider;
}

export async function getAccessToken(): Promise<string | null> {
  try {
    return (await tokenProvider()) || null;
  } catch {
    return null;
  }
}

function messageFrom(body: unknown, fallback: string): string {
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

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = await getAccessToken();
  if (!token) throw new ApiError("Please sign in to continue.", 401);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Can’t reach Edgely right now. Check your connection and try again.", 0);
  }

  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(messageFrom(data, "Something went wrong. Please try again."), response.status);
  }
  return data as T;
}

// One POST /users/me shared by every request that hits the 403 at the same time
// (a page loads several endpoints in parallel).
let provisioning: Promise<PlatformUser> | null = null;

function provisionOnce(): Promise<PlatformUser> {
  provisioning ??= send<PlatformUser>("POST", "/users/me").finally(() => {
    provisioning = null;
  });
  return provisioning;
}

// A brand-new login has no platform user yet; every route except POST /users/me
// answers 403 until it exists. Create it once and retry the original call.
async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  try {
    return await send<T>(method, path, body);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403 && error.message === NO_PLATFORM_USER) {
      await provisionOnce();
      return send<T>(method, path, body);
    }
    throw error;
  }
}

export const usersApi = {
  me: () => request<PlatformUser>("GET", "/users/me"),
  update: (changes: UserUpdate) => request<PlatformUser>("PATCH", "/users/me", changes),
};

export const certificationsApi = {
  list: () => request<Certification[]>("GET", "/certifications"),
};

export const enrollmentsApi = {
  mine: () => request<Enrollment[]>("GET", "/enrollments/me"),
  create: (payload: EnrollmentCreate) => request<Enrollment>("POST", "/enrollments", payload),
  update: (id: number, changes: EnrollmentUpdate) => request<Enrollment>("PATCH", `/enrollments/${id}`, changes),
};

export const tutorApi = {
  context: () => request<LearnerContext>("GET", "/tutor/me/context"),
};

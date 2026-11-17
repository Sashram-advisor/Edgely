import type {
  ForgotPasswordPayload,
  LoginPayload,
  MessageResponse,
  RegisterPayload,
  ResetPasswordPayload,
} from "@/types/auth";

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

async function post<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Lets the backend set an httpOnly session cookie.
      credentials: "include",
      body: JSON.stringify(body),
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

export const authApi = {
  login: (payload: LoginPayload) => post<MessageResponse>("/auth/login", payload),
  register: (payload: RegisterPayload) =>
    post<MessageResponse>("/auth/register", payload),
  forgotPassword: (payload: ForgotPasswordPayload) =>
    post<MessageResponse>("/auth/forgot-password", payload),
  resetPassword: (payload: ResetPasswordPayload) =>
    post<MessageResponse>("/auth/reset-password", payload),
};

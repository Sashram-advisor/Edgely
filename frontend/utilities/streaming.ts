// Client for the tutor's Server-Sent Events endpoint (POST /tutor/chat/stream).
//
// Contract: docs/api/tutor-sse.md (T3). Summary:
//   event: meta  data: {"conversation_id": int, "standalone_query": str}      exactly once, first
//   event: delta data: {"text": str}                                          0..n times
//   event: done  data: {"conversation_id", "message_id", "answer",
//                       "standalone_query", "citations": [...], "usage": {...}}
//   event: error data: {"code", "message", "retryable", "error_id", "detail"}
// The stream ends with exactly one `done` OR one `error`. Frames are separated
// by a blank line.
//
// Failures before the stream starts are plain HTTP errors with a JSON body
// {"detail": "..."}: 401 (no/expired token), 403 (not provisioned / not
// enrolled), 404 (conversation), 422 (bad body), 429 (T4 rate limit, with a
// Retry-After header).

import { supabase } from "./supabase";
import type { ChatDone, TutorStreamError } from "@/types/tutor";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type StreamHandlers = {
  onMeta?: (meta: { conversation_id: number; standalone_query: string }) => void;
  onDelta?: (text: string) => void;
  onDone?: (done: ChatDone) => void;
  // T3: receives a structured, user-safe error instead of a raw string.
  onError?: (error: TutorStreamError) => void;
};

type StreamBody = {
  message: string;
  conversation_id?: number | null;
  certification_id?: number | null;
};

// Error thrown for failures that happen before streaming starts, so callers
// can read the same structured fields as an in-stream `error` event.
export class TutorRequestError extends Error {
  readonly info: TutorStreamError;

  constructor(info: TutorStreamError) {
    super(info.message);
    this.name = "TutorRequestError";
    this.info = info;
  }
}

// Friendly text per stable code. The backend already sends a safe `message`;
// this map lets the UI keep its own wording and still works if the backend
// adds a new code later (falls back to the server's message).
const MESSAGES: Record<string, string> = {
  TUTOR_MODEL_UNAVAILABLE: "The tutor is temporarily unavailable. Please try again in a minute.",
  TUTOR_MODEL_RATE_LIMITED: "The tutor is very busy right now. Please try again in a minute.",
  TUTOR_SAVE_FAILED: "Your answer could not be saved. Please ask again.",
  TUTOR_INTERNAL_ERROR: "Something went wrong while answering. Please try again.",
};

export async function streamTutorChat(
  body: StreamBody,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  let response: Response;
  try {
    response = await fetch(`${API_URL}/tutor/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") return;
    throw new TutorRequestError({
      code: "NETWORK_ERROR",
      message: "Can’t reach the tutor. Check your connection and try again.",
      retryable: true,
    });
  }

  // 401/403/404/422/429 come back as a normal JSON error before streaming starts.
  if (!response.ok) {
    throw new TutorRequestError(await httpError(response));
  }

  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // Normalise CRLF so frame splitting also works behind proxies that rewrite line endings.
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseFrame(frame);
      if (parsed) dispatch(parsed, handlers);
      boundary = buffer.indexOf("\n\n");
    }
  }
}

// Turn a non-2xx response into a TutorStreamError.
async function httpError(response: Response): Promise<TutorStreamError> {
  let detail = `Tutor error (HTTP ${response.status})`;
  try {
    const payload = await response.json();
    if (payload && typeof payload.detail === "string") detail = payload.detail;
  } catch {
    // non-JSON error body; keep the generic message
  }

  if (response.status === 429) {
    // T4: the backend says how long to wait. Header value is whole seconds.
    const retryAfter = Number.parseInt(response.headers.get("Retry-After") ?? "", 10);
    return {
      code: response.headers.get("X-Error-Code") ?? "TUTOR_RATE_LIMITED",
      message: detail,
      retryable: true,
      retryAfterSeconds: Number.isFinite(retryAfter) ? retryAfter : undefined,
    };
  }

  if (response.status === 401) {
    return { code: "HTTP_401", message: "Your session has expired. Please log in again.", retryable: false };
  }

  return { code: `HTTP_${response.status}`, message: detail, retryable: false };
}

function parseFrame(raw: string): { event: string; data: unknown } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    // Lines starting with ":" are SSE comments (keep-alives); ignore them.
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

function dispatch(frame: { event: string; data: unknown }, handlers: StreamHandlers): void {
  const data = frame.data as Record<string, unknown>;
  switch (frame.event) {
    case "meta":
      handlers.onMeta?.({
        conversation_id: data.conversation_id as number,
        standalone_query: data.standalone_query as string,
      });
      break;
    case "delta":
      handlers.onDelta?.(data.text as string);
      break;
    case "done":
      handlers.onDone?.(data as unknown as ChatDone);
      break;
    case "error":
      handlers.onError?.(toStreamError(data));
      break;
    // Unknown events are ignored on purpose, so the backend can add new ones
    // without breaking older clients.
  }
}

// Read an `error` event. Accepts the T3 shape and the pre-T3 {"detail"} shape.
function toStreamError(data: Record<string, unknown>): TutorStreamError {
  const code = typeof data.code === "string" ? data.code : "TUTOR_INTERNAL_ERROR";
  const serverMessage =
    typeof data.message === "string"
      ? data.message
      : typeof data.detail === "string"
        ? data.detail
        : undefined;
  return {
    code,
    message: MESSAGES[code] ?? serverMessage ?? MESSAGES.TUTOR_INTERNAL_ERROR,
    retryable: data.retryable === true,
    errorId: typeof data.error_id === "string" ? data.error_id : undefined,
  };
}

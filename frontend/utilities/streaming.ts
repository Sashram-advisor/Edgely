// Client for the tutor's Server-Sent Events endpoint (POST /tutor/chat/stream).
//
// The backend (routes/tutor.py) emits four event kinds:
//   event: meta  data: {"conversation_id": int, "standalone_query": str}
//   event: delta data: {"text": str}
//   event: done  data: {"conversation_id", "message_id", "answer", "standalone_query",
//                       "citations": [...], "usage": {...}}
//   event: error data: {"detail": str}
// Frames are separated by a blank line.

import { supabase } from "./supabase";
import type { ChatDone } from "@/types/tutor";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type StreamHandlers = {
  onMeta?: (meta: { conversation_id: number; standalone_query: string }) => void;
  onDelta?: (text: string) => void;
  onDone?: (done: ChatDone) => void;
  onError?: (detail: string) => void;
};

type StreamBody = {
  message: string;
  conversation_id?: number | null;
  certification_id?: number | null;
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
    throw new Error("Can’t reach the tutor. Check your connection and try again.");
  }

  // 403/404 come back as a normal JSON error before streaming starts.
  if (!response.ok) {
    let detail = `Tutor error (HTTP ${response.status})`;
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // non-JSON error body; keep the generic message
    }
    throw new Error(detail);
  }

  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

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

function parseFrame(raw: string): { event: string; data: unknown } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
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
      handlers.onError?.(data.detail as string);
      break;
  }
}

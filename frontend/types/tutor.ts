// Types for the tutor chat surface. Mirrors the `done` payload from
// services/ai_tutor/backend/app/chat.py (see _citation_payload and _turn_usage).
// The full SSE contract is in docs/api/tutor-sse.md.

export type Citation = {
  source_id: string; // "S1", "S2", ... matches the [S1] markers in the answer
  chunk_id: number;
  document_title: string;
  domain: string | null;
  source_url: string | null;
  similarity: number;
  rank: number;
};

export type ChatUsage = {
  // Answer call (unchanged since M1).
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  // T4: the optional query-rewrite call and the whole-turn totals.
  // Optional so the type still matches a backend deployed before P1.
  rewrite_input_tokens?: number;
  rewrite_output_tokens?: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
};

export type ChatDone = {
  conversation_id: number;
  message_id: number;
  answer: string;
  standalone_query: string;
  citations: Citation[];
  usage: ChatUsage;
};

// T3: stable error codes sent in the stream's `error` event
// (backend/app/core/tutor_sse.py, TutorStreamErrorCode).
export type TutorStreamErrorCode =
  | "TUTOR_MODEL_UNAVAILABLE"
  | "TUTOR_MODEL_RATE_LIMITED"
  | "TUTOR_SAVE_FAILED"
  | "TUTOR_INTERNAL_ERROR";

// What the chat UI receives for any failure, whether it happened before the
// stream started (HTTP error) or inside it (`error` event).
export type TutorStreamError = {
  // A TutorStreamErrorCode, "TUTOR_RATE_LIMITED" for a 429, or "HTTP_<status>".
  code: string;
  // User-safe text, ready to show.
  message: string;
  // True when asking again later may work.
  retryable: boolean;
  // Seconds to wait before retrying (only for 429 Too Many Requests).
  retryAfterSeconds?: number;
  // Reference id that matches the server log line (only for in-stream errors).
  errorId?: string;
};

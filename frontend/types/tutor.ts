// Types for the tutor chat surface. Mirrors the `done` payload from
// services/ai_tutor/backend/app/chat.py (see _citation_payload).

export type Citation = {
  source_id: string; // "S1", "S2", ... matches the [S1] markers in the answer
  chunk_id: number;
  document_title: string;
  domain: string | null;
  source_url: string | null;
  similarity: number;
  rank: number;
};

export type ChatDone = {
  conversation_id: number;
  message_id: number;
  answer: string;
  standalone_query: string;
  citations: Citation[];
  usage: {
    input_tokens: number;
    output_tokens: number;
    cache_read_input_tokens: number;
  };
};

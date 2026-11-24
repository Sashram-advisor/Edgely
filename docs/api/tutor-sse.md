# Tutor streaming contract — `POST /tutor/chat/stream` (T3)

Status: **stable from P1.** Event names, field names and error codes change only by PR.
Owner: Workstream A. Code: `backend/app/routes/tutor.py`, `backend/app/core/tutor_sse.py`,
`backend/app/core/rate_limit.py`. Client: `frontend/utilities/streaming.ts`.
If this file and the code disagree, the code is wrong.

---

## Request

```
POST /tutor/chat/stream
Authorization: Bearer <supabase-access-token>
Content-Type: application/json
Accept: text/event-stream
```

| Field | Type | Notes |
|---|---|---|
| `message` | string, 1–4000 chars | The learner's question. |
| `conversation_id` | integer or `null` | Continue an existing thread. Omit/`null` to start a new one. |
| `certification_id` | integer or `null` | Scope a *new* thread to one certification. Ignored for an existing thread. |

The learner is taken from the token. A `user_id` in the body is ignored.

`POST /tutor/chat` takes the same body and returns the `done` object below as plain JSON
(no streaming). It has the same rate limit and the same pre-stream errors.

---

## Errors before the stream starts (normal HTTP)

These happen before any model call, so no tokens are spent. Body is always
`{"detail": "<text>"}` (same shape as `docs/api/m1-contract.md`).

| Status | When | Extra headers |
|---|---|---|
| `401` | Missing, invalid or expired token | – |
| `403` | Token valid but no platform user (call `POST /users/me`), or not actively enrolled in the requested certification | – |
| `404` | `conversation_id` does not exist **or belongs to someone else** (never 403, so ids cannot be probed) | – |
| `422` | Body fails validation (empty message, > 4000 chars, wrong types) | – |
| `429` | Per-learner rate limit exceeded (T4) | `Retry-After: <seconds>`, `X-Error-Code: TUTOR_RATE_LIMITED` |

### Rate limit (T4)

* Counted per platform user (from the token), across `/tutor/chat` and `/tutor/chat/stream` together.
* Defaults: **10 questions per rolling minute** and **200 per rolling 24 hours**.
  Configure with `TUTOR_RATE_LIMIT_PER_MINUTE` / `TUTOR_RATE_LIMIT_PER_DAY` in `backend/.env`; `0` disables a window.
* `Retry-After` is whole seconds, rounded up. Waiting that long is enough for the next question to be accepted.
* Rejected requests are not counted, so retrying does not extend the wait.
* A question that is accepted and then fails (403, 404, model error) still counts.
* The counters live in process memory: with N workers the effective limit is N × the setting, and a restart resets them.
* `Retry-After` and `X-Error-Code` are listed in CORS `expose_headers`, so browser JS can read them.

---

## The stream (`200 text/event-stream`)

Each event is one SSE frame: an `event:` line, one `data:` line holding a JSON object, then a blank line.

```
event: <name>
data: <json>

```

Order is always:

```
meta  (exactly 1)  →  delta (0..n)  →  done (exactly 1)  OR  error (exactly 1)
```

After `done` or `error` the server closes the stream. Clients must ignore event names
they do not know (future additions are not breaking changes).

### `meta`

Sent immediately, before the model is called.

```json
{"conversation_id": 42, "standalone_query": "How does S3 Glacier pricing work?"}
```

| Field | Meaning |
|---|---|
| `conversation_id` | The thread this turn belongs to. For a new thread this is the newly created id — store it and send it with the next question. |
| `standalone_query` | The text used for retrieval. Equals `message` unless the follow-up was rewritten (see "Query rewrite" below). |

### `delta`

A piece of the answer text, in order. Concatenate all `text` values to get the answer so far.

```json
{"text": "S3 Glacier charges "}
```

### `done`

The answer is complete **and saved**.

```json
{
  "conversation_id": 42,
  "message_id": 318,
  "answer": "S3 Glacier charges per GB stored [S1] ...",
  "standalone_query": "How does S3 Glacier pricing work?",
  "citations": [
    {
      "source_id": "S1",
      "chunk_id": 17,
      "document_title": "AWS Storage Services",
      "domain": "Cloud Technology and Services",
      "source_url": null,
      "similarity": 0.7123,
      "rank": 1
    }
  ],
  "usage": {
    "input_tokens": 1830,
    "output_tokens": 214,
    "cache_read_input_tokens": 1200,
    "rewrite_input_tokens": 0,
    "rewrite_output_tokens": 0,
    "total_input_tokens": 3030,
    "total_output_tokens": 214
  }
}
```

* `answer` is the final text. It can differ from the concatenated deltas (e.g. a
  "cut off at the length limit" note is appended). Clients should replace the streamed text with it.
* Each `[S<n>]` marker in `answer` has exactly one entry in `citations` with the same `source_id`.
* `usage`: the first three keys describe the answer call (unchanged since M1). T4 added
  `rewrite_*` (the optional rewrite call, `0` when skipped) and `total_*` (the whole turn).
  `total_input_tokens` / `total_output_tokens` are exactly what is stored in
  `messages.tokens_in` / `messages.tokens_out` for the assistant row.

### `error`

Something failed **after** the stream started (the HTTP status is already `200`).

```json
{
  "code": "TUTOR_MODEL_UNAVAILABLE",
  "message": "The tutor is temporarily unavailable. Please try again in a minute.",
  "retryable": true,
  "error_id": "3f2a9c0d7e8b4a51a0c2f6d1e9b7a345",
  "detail": "The tutor is temporarily unavailable. Please try again in a minute."
}
```

| Field | Meaning |
|---|---|
| `code` | One of the stable codes below. Switch on this, never on text. |
| `message` | Fixed, user-safe sentence. **Never contains exception text, SQL, URLs or keys.** |
| `retryable` | `true` when asking the same question again later may work. |
| `error_id` | Random id. The same id is in the server log line (logger `edgely.tutor.stream`) with the full traceback. |
| `detail` | **Deprecated** copy of `message`, kept for clients written before P1. Do not use in new code. |

| Code | Cause | Retryable |
|---|---|---|
| `TUTOR_MODEL_UNAVAILABLE` | Model provider down, overloaded (5xx/529), network error or timeout | yes |
| `TUTOR_MODEL_RATE_LIMITED` | The model provider rate-limited **Edgely** (not the learner) | yes |
| `TUTOR_SAVE_FAILED` | The answer was generated but could not be saved (PostgREST/Supabase error) | yes |
| `TUTOR_INTERNAL_ERROR` | Anything else, including provider 4xx such as a bad API key. A bug or a config problem. | no |

If an `error` arrives, treat the turn as **not** saved: the answer will not reliably appear in
`GET /tutor/conversations/{id}/messages`. (Until Team C's O5 makes each turn one transaction,
a failure while saving citations can leave the message pair saved without its citations.)
Partial `delta` text the client already showed should be discarded or marked as failed.

---

## Query rewrite (T4)

For a follow-up such as "what about Glacier?", retrieval on the raw text would miss the topic,
so the tutor can spend a second, small model call to rewrite it into a standalone question.
`REWRITE_MODE` in `backend/.env` controls this:

| Value | Behaviour |
|---|---|
| `auto` (default) | Rewrite only when there is history **and** the message looks like a follow-up: fewer than 5 words, starts with "what about / how about / and / but / or / why not / then / so", or contains a back-reference such as "it", "this", "that", "they", "same", "more". |
| `always` | Rewrite every message that has history (behaviour before P1). |
| `off` | Never rewrite. |

The first message of a thread is never rewritten in any mode.

---

## The legacy app

`/ai-tutor/chat/stream` (the original unauthenticated tutor app) still emits the pre-P1
`{"detail": str(exc)}` error. It is mounted only with `APP_ENV=local` **and**
`ENABLE_LEGACY_TUTOR_MOUNT=true`, and never in production (T5), so it is not part of this contract.

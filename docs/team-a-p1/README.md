# Team A — P1 delivery (Identity, access & tutor surface)

> 中文版: [README.zh-CN.md](./README.zh-CN.md)

Base: `main @ 97b203d` (after PR #15, *Teammate A P0*).
Source of the task list: *Edgely readiness checklist v2, 2026-11-17*, section 03 (Team A).

| ID | Item | Priority | Status |
|---|---|---|---|
| R6 | Frontend can install its own auth client | P1 | Dependency was added in P0; verified by `npm run build` (see "Verify") |
| A5 | Dashboard route guard | P1 | Done |
| T3 | SSE contract documented; errors sanitised to stable codes | P1 | Done |
| T4 | Per-user rate limit (429 + Retry-After); tokens per turn recorded | P1 | Done |
| T5 | Only `/tutor` reachable with `APP_ENV=production` | P1 | Done |

Team A's P0 items (R3, A1–A4, T1, T2, O4) were merged in PR #15. A6 is P2 and not needed,
because A1 chose option (a): the browser talks to Supabase Auth directly.

---

## 1. What each task changes

### R6 — Supabase client in the frontend
`frontend/package.json` already lists `@supabase/supabase-js ^2.49.0` (added in P0).
P1 only closes the "done when": `npm install && npm run build` must pass with the client in place.
Nothing else changes.

### A5 — Dashboard route guard
**Problem:** anyone who typed `/dashboard` saw the dashboard.
**Fix:** a client-side guard.

* The Supabase session lives in the browser's `localStorage`, not a cookie, so server code
  (middleware / server components) cannot see it. The guard has to run in the browser.
* While checking, the guard shows "Checking your session…", never the page, so nothing private flashes.
* No session → `router.replace("/login?next=/dashboard")`. `replace`, so Back does not loop.
* Sign-out in any tab → immediate redirect (Supabase `SIGNED_OUT` event).
* After login, the user returns to `next`. `safeNextPath()` only accepts same-site paths, so
  `?next=https://evil.example` cannot be used as an open redirect.
* The guard is a UX gate. The real security boundary is still the backend: every API call needs a
  valid Bearer token (A3).

### T3 — SSE contract and sanitised errors
**Problem:** the event format existed only in code, and on failure the stream sent
`{"detail": str(exc)}`, i.e. internal exception text (SQL, URLs, possibly keys) reached the browser.
**Fix:**

* The full contract is written in [`docs/api/tutor-sse.md`](../api/tutor-sse.md).
* `backend/app/core/tutor_sse.py` turns any in-stream exception into
  `{"code", "message", "retryable", "error_id", "detail"}`, with one of four stable codes:
  `TUTOR_MODEL_UNAVAILABLE`, `TUTOR_MODEL_RATE_LIMITED`, `TUTOR_SAVE_FAILED`, `TUTOR_INTERNAL_ERROR`.
  `message` is a fixed sentence and never contains exception text.
* The real exception and traceback go to the server log (logger `edgely.tutor.stream`) with the same
  `error_id`, so a user's "Reference: 3f2a9c0d" can be matched to the log line.
* `detail` is kept as a deprecated copy of `message`, so pre-P1 clients still work.
* Frontend `streaming.ts` reads the new shape and maps codes to friendly text.

### T4 — Rate limit and token recording
**Problem:** every question made two model calls (rewrite + answer) and nothing limited a user.
**Fix:**

* `backend/app/core/rate_limit.py`: a per-learner sliding-window limit on `/tutor/chat` and
  `/tutor/chat/stream` (shared). Defaults: 10 per minute, 200 per day (`TUTOR_RATE_LIMIT_PER_MINUTE`,
  `TUTOR_RATE_LIMIT_PER_DAY`). Over the limit → `429` with `Retry-After` and `X-Error-Code: TUTOR_RATE_LIMITED`.
  The key is the verified user id from the token. The check runs before any model call.
* `main.py`: CORS `expose_headers` now includes `Retry-After` and `X-Error-Code`, otherwise browser JS cannot read them.
* `chat.py`:
  * `needs_rewrite()` skips the rewrite call when the message is clearly standalone
    (`REWRITE_MODE=auto`, default). Most questions now cost one model call. `always` restores the old behaviour.
  * Tokens of **both** calls are recorded: the assistant row's `tokens_in` / `tokens_out` now hold the turn total,
    the `done` event's `usage` adds `rewrite_*` and `total_*` keys (old keys unchanged), and one log line per turn
    is written to `edgely.tutor.usage`.
* The chat UI shows "You can ask again in N s." on a 429.

### T5 — One tutor surface in production
**Problem:** three tutor surfaces existed: `/tutor` (authenticated), `/ai-tutor` (legacy, no auth,
`GET /users` lists every learner's email) and `/local-tutor` (no auth).
**Fix (on top of O4's two-switch rule):**

* `backend/.env.example` now ships `APP_ENV=production` (was `local`). Copying the template to a server can no
  longer turn on local-only behaviour. Developers opt in to `local` on their own machine.
* `merged_main.py` inspects the routes actually registered at startup. If `APP_ENV` is not `local` and any
  `/ai-tutor` or `/local-tutor` route exists, the server refuses to start (fail closed).
* `local_only_main.py` (a separate entry point that serves only `/local-tutor`) refuses to start unless `APP_ENV=local`.
* `integration_tests/test_merge.py::test_local_tutor_routes_are_registered` asserted the pre-O4 behaviour and
  failed after O4. It is replaced by `test_local_tutor_routes_are_off_by_default`.

---

## 2. Files touched in P1

| File | New / changed | Task | What it is |
|---|---|---|---|
| `frontend/components/auth/RequireAuth.tsx` | new | A5 | Client-side route guard component |
| `frontend/utilities/redirect.ts` | new | A5 | `safeNextPath()` / `loginUrlFor()`: safe "return after login" |
| `frontend/app/dashboard/page.tsx` | changed | A5 | Wraps `<Dashboard />` in `<RequireAuth>` |
| `frontend/components/auth/LoginForm.tsx` | changed | A5 | After login, go to `?next=` instead of always `/dashboard` |
| `backend/app/core/tutor_sse.py` | new | T3 | SSE frame formatting, error codes, sanitising |
| `docs/api/tutor-sse.md` | new | T3 | Written SSE contract |
| `frontend/utilities/streaming.ts` | changed | T3, T4 | Reads coded errors; reads 429 `Retry-After` |
| `frontend/types/tutor.ts` | changed | T3, T4 | `TutorStreamError`, extended `ChatUsage` |
| `frontend/components/chat/TutorChat.tsx` | changed | T3, T4 | Shows coded errors, wait time and reference id |
| `backend/app/routes/tutor.py` | changed | T3, T4 | Uses rate-limit dependency and sanitised error event |
| `backend/app/core/rate_limit.py` | new | T4 | Sliding-window limiter + FastAPI dependency |
| `backend/app/core/config.py` | changed | T4 | `tutor_rate_limit_per_minute`, `tutor_rate_limit_per_day` |
| `backend/app/main.py` | changed | T4 | CORS `expose_headers` |
| `services/ai_tutor/backend/app/chat.py` | changed | T4 | `needs_rewrite()`, rewrite token capture, `_turn_usage()`, usage log |
| `services/ai_tutor/backend/app/config.py` | changed | T4 | `rewrite_mode` setting |
| `backend/.env.example` | changed | T4, T5 | `APP_ENV=production`, `REWRITE_MODE`, `TUTOR_RATE_LIMIT_*` |
| `backend/app/merged_main.py` | changed | T5 | `registered_paths()`, `_assert_single_tutor_surface()` |
| `backend/app/local_only_main.py` | changed | T5 | Refuses to start unless `APP_ENV=local` |
| `backend/tests/unit/test_rate_limit.py` | new | T4 | Limiter unit tests (fake clock) |
| `backend/tests/unit/test_tutor_sse.py` | new | T3 | Sanitising and classification tests |
| `backend/tests/unit/test_config_safety.py` | changed | T4, T5 | Local-tutor switches, template default, limit defaults |
| `integration_tests/test_tutor_p1.py` | new | T3, T4 | 429 + Retry-After, SSE order, sanitised error, rewrite heuristic, usage |
| `integration_tests/test_tutor_startup.py` | changed | T5 | Production/development expose only `/tutor`; local-only entry refuses |
| `integration_tests/test_merge.py` | changed | T5 | Fixes the stale `/local-tutor` assertion |
| `integration_tests/test_tutor_auth.py` | changed | T4 | Resets the limiter between tests |

---

## 3. Verify

```bash
# Backend (from the repo root, in the virtualenv built from Team C's R1 manifest)
cd backend && python -m pytest tests/unit -q && cd ..
python -m pytest integration_tests -q

# Frontend (R6 done-when)
cd frontend
npm install
npm run build
```

Manual checks:

| Task | Check | Expected |
|---|---|---|
| A5 | Log out, open `http://localhost:3000/dashboard` | Redirect to `/login?next=%2Fdashboard`; after login you land on `/dashboard` |
| A5 | Open `/login?next=https://evil.example`, log in | You land on `/dashboard`, not the external site |
| T3 | Set an invalid `ANTHROPIC_API_KEY`, ask the tutor | UI shows a fixed message + "Reference: xxxxxxxx"; the server log has the traceback with the same id; the browser never sees the exception text |
| T4 | Set `TUTOR_RATE_LIMIT_PER_MINUTE=2`, ask 3 questions quickly | Third gets `429` with `Retry-After`; UI shows "You can ask again in N s." |
| T4 | Ask two questions in one thread, then `select tokens_in, tokens_out from messages where role='assistant' order by id desc limit 2` | Values match `usage.total_input_tokens` / `total_output_tokens` of the `done` events |
| T5 | `APP_ENV=production ENABLE_LEGACY_TUTOR_MOUNT=true ENABLE_LOCAL_TUTOR_MOUNT=true uvicorn app.merged_main:app` | `/ai-tutor/*` and `/local-tutor/*` return 404; `/tutor/*` works |
| T5 | `APP_ENV=production uvicorn app.local_only_main:app` | Fails at startup with "only runs with APP_ENV=local" |

---

## 4. Things to tell the team

* **`.env` change for developers:** the template now says `APP_ENV=production`. If you use the Streamlit dev UI
  (`/ai-tutor`) or the Ollama tutor (`/local-tutor`), set `APP_ENV=local` in **your own** `backend/.env`.
* **Team C (O5, L5):** T4 edits `_persist()` in `services/ai_tutor/backend/app/chat.py` (adds the rewrite tokens
  to `tokens_in` / `tokens_out`). O5 (one transaction per turn) and L5 (assistant id from the insert) touch the
  same function. Please rebase on this change, or tell Team A which PR goes first.
* **Rate limit limitation:** counters are in process memory. With N uvicorn workers the effective limit is
  N × the setting, and a restart resets it. Fine for the MVP (one process); use Redis before scaling out.
* **Legacy app:** `/ai-tutor/chat/stream` still sends raw exception text, because that vendored app is kept
  unmodified. It can only run with `APP_ENV=local` plus an explicit flag, never in production.
* **Frontend contract:** the `error` event changed shape (old `detail` kept as an alias), and `usage` gained new
  keys. Anyone else reading the stream should switch on `code`.

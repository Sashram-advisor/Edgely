# AI Tutor merge — handoff guide

This repository is the Edgely platform with two additional, independently
developed tutor implementations folded in:

| Source | What it contributes | Location in this repo |
| --- | --- | --- |
| `Sashram-advisor/Edgely` (`da2d784`) | Host platform: FastAPI core, Supabase/Postgres schema, auth, CORS, empty feature scaffolding | original application tree, unchanged (root README extended with merge notes) |
| `KhaTruong760/AI_Tutor_Test` (`7121844`) | Course RAG tutor: learner context, enrollment scoping, pgvector retrieval, Claude streaming, citations, conversation history, Streamlit UI, embedding script, eval skeleton | `services/ai_tutor/` (verbatim) |
| `Ai Tutor.zip` (SHA-256 `E9B7E7EE…D5B2`) | Offline Ollama tutor over a bundled AWS Cloud Practitioner study guide | `services/local_tutor/` (verbatim), plus an additive HTTP bridge |

No git commit or push was made. The working tree contains the merge; the
reviewer/next team can inspect it, run it, and commit it themselves.

## 1. Design rule: vendor, don't rewrite

The two imported codebases are copied **verbatim** into `services/`. Their
original package layout and imports are preserved:

```
services/ai_tutor/
  backend/app/{main,chat,context,config,db,embeddings,prompt,retrieval}.py
  ui/streamlit_app.py
  scripts/embed_chunks.py
  migrations/001_pgvector_rag.sql
  requirements.txt

services/local_tutor/
  main.py
  data/study_material.txt
```

The only changes to those trees are the exclusion of generated/local artifacts
(`.venv`, `__pycache__`, `.git`) and project-specific `.mcp.json`, `.env` and
Supabase CLI temp/config files, because they contain secrets or machine-local
links. No application line was edited.

Everything else in this merge is *additive*:

| Added path | Purpose |
| --- | --- |
| `backend/app/integrations/ai_tutor_mount.py` | Loads the vendored app under the private package name `edgely_ai_tutor` (so its relative imports still work and it cannot collide with Edgely's `backend/`) |
| `backend/app/integrations/local_tutor_api.py` | FastAPI bridge exposing the zip's Ollama RAG over HTTP |
| `backend/app/merged_main.py` | Composition root: Edgely app + `/ai-tutor` mount + `/local-tutor` router |
| `backend/app/local_only_main.py` | Optional entry point for the local tutor with no Edgely database |
| `backend/app/database/migrations/20261102000100_ai_tutor_pgvector.sql` | Additive pgvector/citation columns and `match_document_chunks` RPC |
| `backend/.env.example` | One environment template for both codebases |
| `requirements-merged.txt` | Unified runtime dependencies |
| `ui/merged_app.py` | One Streamlit UI with both engines |
| `integrations/` | Docker composition and local start script |
| `integration_tests/` | Offline structural/unit checks |
| `docs/AI_TUTOR_MERGE.md` | This document |

Edgely's `backend/app/main.py`, `core/*`, routes, AI placeholders and frontend
scaffold are untouched. `uvicorn app.main:app` still runs the original
Edgely-only service.

## 2. Runtime architecture

```
                    ┌─────────────────────────────┐
  Browser ────────▶ │  ui/merged_app.py (8501)    │
                    │  mode = Course | Local      │
                    └─────────────┬───────────────┘
                                  │ HTTP
                    ┌─────────────▼───────────────┐
                    │  app.merged_main:app (8000) │
                    │  Edgely host app            │
                    │  ├─ /health (original)      │
                    │  ├─ /ai-tutor/*  (mounted)  │
                    │  └─ /local-tutor/* (bridge) │
                    └───────┬─────────────┬───────┘
                            │             │
             Supabase/Postgres         Ollama (11434)
             + Gemini embeddings       nomic-embed-text
             + Claude chat             llama3.2:3b
```

The two engines are intentionally separate at the edges:

* Course tutor uses Supabase PostgREST with a server-side secret key and the
  `match_document_chunks` SQL function. It is scoped to the learner's active
  enrollments and stores conversations/citations in Edgely's existing tables.
* Local tutor uses only the bundled text file and a local Ollama daemon. It
  needs no cloud credentials, which makes it useful for demos and offline
  development.

## 3. Endpoint map

**Authenticated routes** - these are what clients use. Every one needs a
Supabase access token (`Authorization: Bearer <token>`); the learner always
comes from the token, never from the body. Full contract:
[docs/api/m1-contract.md](api/m1-contract.md).

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/users/me` | Create my platform user on first login (idempotent) |
| GET / PATCH | `/users/me` | Read / update my profile |
| GET | `/certifications` | Active certification catalog |
| GET | `/enrollments/me` | My enrollments |
| POST | `/enrollments` | Enroll in a certification |
| PATCH | `/enrollments/{id}` | Pause, resume, complete or abandon |
| POST | `/tutor/chat` | Tutor answer (JSON) |
| POST | `/tutor/chat/stream` | Tutor answer (SSE: `meta`, `delta`*, `done` or `error`) |
| GET | `/tutor/me/context` | My learner context as the tutor sees it |
| GET | `/tutor/conversations` | My conversations, newest first |
| GET | `/tutor/conversations/{id}/messages` | Messages and citations of my conversation |

A valid token with no platform user yet gets `403` - call `POST /users/me`
once. A learner with no active enrollment gets `403` from the tutor routes.

**Unauthenticated routes**

| Method | Path | Source |
| --- | --- | --- |
| GET | `/health` | Edgely |
| GET | `/health/tutor` | `ok` / `disabled` / `error` |
| GET | `/docs` | Edgely merged OpenAPI |
| GET | `/local-tutor/health`, `/local-tutor/material` | Local bridge |
| POST | `/local-tutor/chat` | Local bridge |
| * | `/ai-tutor/*` | **Legacy, local only - see below** |

### The legacy `/ai-tutor` mount

The upstream AI Tutor app trusts a `user_id` sent by the caller and
`GET /ai-tutor/users` lists every learner's email. It is mounted **only** when
both of these are set in `backend/.env`:

```
APP_ENV=local
ENABLE_LEGACY_TUTOR_MOUNT=true
```

`APP_ENV` defaults to `production` in code, and in production the mount stays
off even if the flag is true. Turn it on only on your own machine, and only for
the Streamlit UIs below. Its internal paths are unchanged; only the mount prefix
is new.

## 4. Database changes

The whole schema is built with Alembic, in one command, from `backend/`:

```powershell
cd backend
python -m alembic upgrade head
```

It reads `DATABASE_URL` from `backend/.env`. The baseline revision applies
`Database_inital` and the pgvector file below; the next revision adds the
hot-path indexes. Running it again is a no-op. `Database_inital` on its own is
also safe to re-run (its foreign keys are only added when missing).

The pgvector part is
`backend/app/database/migrations/20261102000100_ai_tutor_pgvector.sql`.
It is idempotent and only adds:

* `document_chunks.embedding extensions.vector(1536)`
* `document_chunks.embedding_model`, `content_hash`, `embedded_at`
* HNSW and document-id indexes
* `message_citations.similarity`, `message_citations.rank`
* `public.match_document_chunks(...)`, executable by `service_role` only

`services/ai_tutor/migrations/001_pgvector_rag.sql` is the same upstream
migration, kept for provenance.

After the migration, populate embeddings for the seeded chunks:

```powershell
cd services/ai_tutor
$env:ENV_FILE = "../../backend/.env"
python scripts/embed_chunks.py
```

`embed_chunks.py` is idempotent: it re-embeds only chunks whose text or
embedding model changed.

## 5. Configuration

```powershell
Copy-Item backend/.env.example backend/.env
# edit backend/.env
```

Required for the course tutor:

* `DATABASE_URL` — Edgely's Postgres/Supabase connection string
* `SUPABASE_URL` — project URL
* `SUPABASE_SECRET_KEY` — server-side service-role key (never browser-exposed)
* `ANTHROPIC_API_KEY`
* `GEMINI_API_KEY` (or `EMBEDDING_PROVIDER=openai` + `OPENAI_API_KEY`)

Required for the local tutor:

* a running Ollama at `OLLAMA_BASE_URL` (default `http://localhost:11434`)
* `ollama pull nomic-embed-text`
* `ollama pull llama3.2:3b`

Environment switches:

* `APP_ENV` - `local`, `development` or `production`. The code default is
  `production`; `.env.example` sets `local` for development machines.
* `ENABLE_LEGACY_TUTOR_MOUNT` - `false` by default. Mounts the unauthenticated
  `/ai-tutor` app only together with `APP_ENV=local` (see section 3).

Optional Edgely-only values (`SUPABASE_JWT_SECRET`, Azure/OpenAI settings,
`CORS_ORIGINS`, pool sizes) are documented inline in `.env.example`.

Both config systems read `backend/.env` when the merged API is started from
`backend/`. The AI Tutor scripts read the same file through `ENV_FILE` as shown
above.

## 6. Run it

### Local (two terminals)

```powershell
# once, repository root
pip install -r requirements-merged.txt
pip install -r requirements-ui.txt

# terminal 1 — merged API
cd backend
python -m uvicorn app.merged_main:app --reload --port 8000

# terminal 2 — merged UI
streamlit run ui/merged_app.py
```

Open <http://localhost:8501>. The sidebar switches between **Course tutor** and
**Local Ollama**. The Streamlit UIs call the legacy `/ai-tutor` mount, so
**Course tutor** mode needs `APP_ENV=local` and `ENABLE_LEGACY_TUTOR_MOUNT=true`
in `backend/.env` (local machines only).

The original AI Tutor UI is still available unchanged:

```powershell
$env:API_URL = "http://localhost:8000/ai-tutor"
streamlit run services/ai_tutor/ui/streamlit_app.py
```

### Docker Compose

```powershell
Copy-Item backend/.env.example backend/.env
# fill backend/.env first
docker compose -f integrations/docker-compose.yml up --build
```

Services:

* `api` → <http://localhost:8000>
* `web` → <http://localhost:8501>
* `ollama` (profile `local-ai`) → <http://localhost:11434>

With the Ollama profile:

```powershell
docker compose -f integrations/docker-compose.yml --profile local-ai up --build
docker compose -f integrations/docker-compose.yml exec ollama ollama pull nomic-embed-text
docker compose -f integrations/docker-compose.yml exec ollama ollama pull llama3.2:3b
```

### Local-only (no Supabase needed)

If you only want to exercise the zip functionality, skip the Edgely database
entirely:

```powershell
cd backend
uvicorn app.local_only_main:app --reload --port 8001
```

```powershell
# second terminal, repository root
$env:API_URL = "http://localhost:8001"
streamlit run ui/merged_app.py
```

The **Local Ollama** mode works; the **Course tutor** mode reports that
`/ai-tutor` is unavailable, which is expected in this mode.

### Zip CLI (preserved)

```powershell
cd services/local_tutor
pip install -r requirements.txt
ollama serve
python main.py
```

## 7. Tests

Offline checks (no database, no API keys, no Ollama), from the repository root:

```powershell
pip install -r requirements-dev.txt
pytest -q integration_tests backend/tests
```

They cover the merge structure, the `/ai-tutor` safety switches, the
`/users`, `/certifications` and `/enrollments` routes, and `link_user.py`.

Database tests are skipped unless you point them at a **disposable** Postgres
(they create and drop their own schema or database):

```powershell
$env:EDGELY_TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/edgely_test"
$env:EDGELY_TEST_ADMIN_URL    = "postgresql://postgres:postgres@localhost:5432/postgres"  # migration test
pytest -q backend/tests
```

Shared fixtures (`run_db`, `seed_sql`) live in `backend/tests/conftest.py`.

With live services, smoke-test manually:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/health/tutor
curl http://localhost:8000/local-tutor/health
```

Then use the UI for a streaming course answer and a local Ollama answer.

## 8. Deliberate limitations / notes for the next team

1. **The upstream tutor app has no auth; use `/tutor/*`.** The vendored app
   takes `user_id` from the request body. The authenticated wrapper in
   `backend/app/routes/tutor.py` (`/tutor/*`) takes the learner from the
   Supabase token instead. The raw app is only mounted at `/ai-tutor` with
   `APP_ENV=local` and `ENABLE_LEGACY_TUTOR_MOUNT=true`; never enable that on a
   deployed server.
2. **Two database access styles.** Edgely uses SQLAlchemy/asyncpg; the AI Tutor
   uses Supabase PostgREST. Both point at the same database, but the AI Tutor
   needs `SUPABASE_URL`/`SUPABASE_SECRET_KEY` in addition to `DATABASE_URL`.
3. **Streamlit is the operational UI.** `frontend/` is still Edgely's empty
   Next.js scaffold. Replacing it is a separate frontend task; the merged UI
   lives in `ui/merged_app.py`.
4. **The zip's original splitter is preserved in the CLI.** The bridge recognises
   both `##` and `Topic N:` headings, because the bundled material uses the
   latter; this is the only behavioural improvement in the bridge. The CLI in
   `services/local_tutor/main.py` is untouched and keeps its original splitter.
5. **Upstream incomplete files were preserved.** `services/ai_tutor/eval/run_eval.py`
   and `scripts/ingest_document.py` are empty in the upstream repository. They
   were not invented or modified here.
6. **Local tutor responses are non-streaming.** The bridge returns one JSON
   answer; the course tutor keeps its original SSE streaming endpoint.
## 9. Handoff checklist

- [ ] Copy `backend/.env.example` → `backend/.env` and fill secrets.
- [ ] Build the schema: `cd backend; python -m alembic upgrade head`.
- [ ] Run `scripts/embed_chunks.py` against the seeded `document_chunks`.
- [ ] Verify `d.ready` documents exist for the learner's certifications.
- [ ] Link a real login: `python scripts/link_user.py --email you@example.com`
      (from `backend/`), or call `POST /users/me` with its token.
- [ ] Start the merged API with `app.merged_main:app`.
- [ ] Start `ui/merged_app.py` and exercise both modes (local machine only).

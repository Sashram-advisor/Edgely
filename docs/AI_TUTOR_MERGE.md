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

| Method | Path | Source |
| --- | --- | --- |
| GET | `/health` | Edgely (unchanged) |
| GET | `/docs` | Edgely merged OpenAPI (includes `/local-tutor`) |
| GET | `/ai-tutor/docs` | AI Tutor's own OpenAPI |
| POST | `/ai-tutor/chat` | AI Tutor (unchanged) |
| POST | `/ai-tutor/chat/stream` | AI Tutor (unchanged, SSE) |
| GET | `/ai-tutor/users` | AI Tutor (unchanged) |
| GET | `/ai-tutor/users/{id}/context` | AI Tutor (unchanged) |
| GET | `/ai-tutor/users/{id}/conversations` | AI Tutor (unchanged) |
| GET | `/ai-tutor/conversations/{id}/messages` | AI Tutor (unchanged) |
| GET | `/local-tutor/health` | New bridge |
| GET | `/local-tutor/material` | New bridge (section inventory) |
| POST | `/local-tutor/chat` | New bridge |

The AI Tutor's internal paths are unchanged; only the mount prefix is new. This
is why its Streamlit UI works with a single `API_URL` that includes
`/ai-tutor`.

## 4. Database changes

Edgely's base schema already has every table the AI Tutor expects, except the
pgvector/citation additions. Apply:

```
backend/app/database/migrations/20261102000100_ai_tutor_pgvector.sql
```

in the Supabase SQL editor (or with `supabase db push` if the project is linked).
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
**Local Ollama**.

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

Offline checks (no database, no API keys, no Ollama):

```powershell
pip install -r requirements-dev.txt
pytest -q integration_tests
```

They assert that:

* Edgely's `/health` and docs routes still exist,
* the AI Tutor app is mounted and its relative imports survived relocation,
* all `/local-tutor` routes are registered,
* the zip study material is split into topic sections,
* cosine similarity and citation parsing behave correctly,
* the pgvector migration contains the required additions.

With live services, smoke-test manually:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/ai-tutor/users
curl http://localhost:8000/local-tutor/health
```

Then use the UI for a streaming course answer and a local Ollama answer.

## 8. Deliberate limitations / notes for the next team

1. **No auth on tutor routes.** The upstream AI Tutor has no authentication and
   takes `user_id` from the request body. Edgely's `core/auth_provider.py` is
   available but is not wired into these routes because that would require
   editing vendored code. Do not expose `/ai-tutor` publicly until a wrapper or
   dependency is added.
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
7. **No git commit/push.** The `.git` directory is the original Edgely clone;
   the merge is intentionally left as uncommitted working-tree changes.

## 9. Handoff checklist

- [ ] Copy `backend/.env.example` → `backend/.env` and fill secrets.
- [ ] Run the pgvector migration in Supabase.
- [ ] Run `scripts/embed_chunks.py` against the seeded `document_chunks`.
- [ ] Verify `d.ready` documents exist for the learner's certifications.
- [ ] Start the merged API with `app.merged_main:app`.
- [ ] Start `ui/merged_app.py` and exercise both modes.
- [ ] Review `git status`; commit only when the receiving team is ready.

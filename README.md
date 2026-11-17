# Edgely
Learn Smarter. Certify Faster.
Your AI Certification Coach.
The Intelligent Learning Edge.

## Merged AI Tutor

This working tree merges two tutor implementations into Edgely:

* **Course RAG tutor** from `KhaTruong760/AI_Tutor_Test` — learner context,
  enrollment-scoped pgvector retrieval, Claude streaming answers, citations and
  conversation history. Vendored verbatim in `services/ai_tutor/` and served
  through the authenticated `/tutor/*` routes.
* **Local Ollama tutor** from `Ai Tutor.zip` — offline AWS study-material RAG.
  Vendored verbatim in `services/local_tutor/` and exposed at `/local-tutor`.

The merged API entry point is `app.merged_main:app`; the original
`app.main:app` still runs Edgely alone. The operational UI is
`ui/merged_app.py` (Streamlit) with a switch between both engines.

## Quick start

From an empty database to a learner who can ask the tutor a question:

```powershell
# 1. Settings (repository root). Fill in DATABASE_URL, SUPABASE_URL,
#    SUPABASE_SECRET_KEY, ANTHROPIC_API_KEY and GEMINI_API_KEY.
Copy-Item backend/.env.example backend/.env
pip install -r requirements-dev.txt

# 2. Build the schema (safe to run again)
cd backend
python -m alembic upgrade head

# 3. Start the API
python -m uvicorn app.merged_main:app --reload --port 8000
```

4. **Sign up** through Supabase Auth (the frontend, or the Supabase dashboard).
5. **Become a platform user:** call `POST /users/me` with the access token, or
   link an existing login from `backend/`:
   `python scripts/link_user.py --email you@example.com`
6. **Enroll:** `GET /certifications`, then `POST /enrollments` with a
   `certification_id`.
7. **Ask the tutor:** `POST /tutor/chat` with the same token.

Every route except `/health` needs `Authorization: Bearer <supabase token>`.
The full request/response contract is in
[docs/api/m1-contract.md](docs/api/m1-contract.md); interactive docs are at
<http://localhost:8000/docs>.

### Environment switches

* `APP_ENV` - `local`, `development` or `production` (code default:
  `production`).
* `ENABLE_LEGACY_TUTOR_MOUNT` - the original tutor app has **no
  authentication**. It is mounted at `/ai-tutor` only when this is `true` **and**
  `APP_ENV=local`. The Streamlit UI needs it; never enable it on a server.

```powershell
# optional, local machine only: the Streamlit UI (repository root)
streamlit run ui/merged_app.py
```

### Tests

```powershell
pytest -q integration_tests backend/tests
```

Database tests are skipped unless `EDGELY_TEST_DATABASE_URL` (and, for the
migration test, `EDGELY_TEST_ADMIN_URL`) point at a disposable Postgres.

Read [docs/AI_TUTOR_MERGE.md](docs/AI_TUTOR_MERGE.md) for the architecture,
configuration, Docker Compose usage, known limitations and handoff checklist.

# Edgely
Learn Smarter. Certify Faster.
Your AI Certification Coach.
The Intelligent Learning Edge.

## Merged AI Tutor

This working tree merges two tutor implementations into Edgely:

* **Course RAG tutor** from `KhaTruong760/AI_Tutor_Test` — learner context,
  enrollment-scoped pgvector retrieval, Claude streaming answers, citations and
  conversation history. Vendored verbatim in `services/ai_tutor/` and mounted at
  `/ai-tutor`.
* **Local Ollama tutor** from `Ai Tutor.zip` — offline AWS study-material RAG.
  Vendored verbatim in `services/local_tutor/` and exposed at `/local-tutor`.

The merged API entry point is `app.merged_main:app`; the original
`app.main:app` still runs Edgely alone. The operational UI is
`ui/merged_app.py` (Streamlit) with a switch between both engines.

Quick start:

```powershell
Copy-Item backend/.env.example backend/.env   # fill in secrets
pip install -r requirements-dev.txt
cd backend
uvicorn app.merged_main:app --reload --port 8000
```

```powershell
# second terminal, repository root
streamlit run ui/merged_app.py
```

Read [docs/AI_TUTOR_MERGE.md](docs/AI_TUTOR_MERGE.md) for the architecture,
database migration, configuration, Docker Compose usage, tests, known
limitations and handoff checklist.

No commit or push was performed; the merge is intentionally left in the working
tree for review.

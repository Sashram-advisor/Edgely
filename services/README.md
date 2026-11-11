# Vendored tutor services

These trees are imports from two other repositories. They are deliberately kept
in their original layout so their imports, scripts and UIs keep working.

## `ai_tutor/`

From `KhaTruong760/AI_Tutor_Test` at commit
`7121844fd9022357f1ec362c0e54edab881c5316`.

Run it standalone:

```powershell
cd services/ai_tutor
$env:ENV_FILE = "../../backend/.env"
python -m uvicorn backend.app.main:app --reload --port 8001
```

Run its original UI:

```powershell
$env:API_URL = "http://localhost:8001"
streamlit run ui/streamlit_app.py
```

Run its embedding backfill:

```powershell
$env:ENV_FILE = "../../backend/.env"
python scripts/embed_chunks.py
```

In the merged app it is loaded under the private package name
`edgely_ai_tutor` and mounted at `/ai-tutor`; see
`backend/app/integrations/ai_tutor_mount.py`.

## `local_tutor/`

From `Ai Tutor.zip` (SHA-256
`E9B7E7EE2473EB5A18D78DD2BC1ACB8A11D563DCD63099D71381199AC5EFD5B2`).

The CLI is unchanged:

```powershell
cd services/local_tutor
pip install -r requirements.txt
python main.py
```

The merged HTTP bridge lives in
`backend/app/integrations/local_tutor_api.py`; it reads
`services/local_tutor/data/study_material.txt` but does not modify or import
`main.py`.

## Rules for future changes

* Do not refactor these trees in place. If upstream changes, replace the whole
  tree and record the new commit/hash in `docs/AI_TUTOR_MERGE.md`.
* Put integration glue in `backend/app/integrations/` or `ui/`.
* Keep secrets in `backend/.env`; never add `.env`, `.venv` or `.mcp.json` here.

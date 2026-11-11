# Merged Streamlit UI

`merged_app.py` is the operational UI for the merged platform. It has two modes:

* **Course tutor (Edgely RAG)** — streaming Claude answers with citations,
  learner context, enrollment scoping and past conversations.
* **Local Ollama (offline)** — the `Ai Tutor.zip` tutor over the bundled AWS
  study material.

```powershell
# from the repository root, with the merged API running on :8000
streamlit run ui/merged_app.py
```

Environment overrides:

| Variable | Default |
| --- | --- |
| `API_URL` | `http://localhost:8000` |
| `AI_TUTOR_API_URL` | `${API_URL}/ai-tutor` |
| `LOCAL_TUTOR_API_URL` | `${API_URL}/local-tutor` |

The original AI Tutor UI remains untouched at
`services/ai_tutor/ui/streamlit_app.py`. It can be run with
`API_URL=http://localhost:8000/ai-tutor`.

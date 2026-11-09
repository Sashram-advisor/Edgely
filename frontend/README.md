# Frontend scaffold

This directory is Edgely's original Next.js scaffold (`app/`, `components/`,
`hooks/`, `types/`, `utilities/`). It was empty at the merge baseline and is
left untouched.

The working UI for the merged tutor is `../ui/merged_app.py` (Streamlit). It
was added rather than filling in this scaffold, because inventing a Next.js
application would have changed the scope of the merge and could not be verified
against the original repository.

When the frontend team is ready, the backend contract is:

* `POST /ai-tutor/chat/stream` — SSE course tutor
* `GET /ai-tutor/users` and `/ai-tutor/users/{id}/context`
* `GET /ai-tutor/users/{id}/conversations`
* `GET /ai-tutor/conversations/{id}/messages`
* `POST /local-tutor/chat` — non-streaming local Ollama tutor

See `docs/AI_TUTOR_MERGE.md` for the full endpoint map.

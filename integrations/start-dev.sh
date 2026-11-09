#!/usr/bin/env bash
# Start the merged API and UI for local development.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-8501}"

if [[ ! -f "$ROOT/backend/.env" ]]; then
  echo "warning: backend/.env is missing; copy backend/.env.example and fill it in" >&2
fi

cleanup() {
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "${UI_PID:-}" ]] && kill "$UI_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$ROOT/backend"
  python -m uvicorn app.merged_main:app --reload --port "$API_PORT"
) &
API_PID=$!

if [[ "${NO_UI:-0}" != "1" ]]; then
  (
    cd "$ROOT"
    API_URL="http://localhost:$API_PORT" \
      streamlit run ui/merged_app.py --server.port "$UI_PORT"
  ) &
  UI_PID=$!
fi

echo "API: http://localhost:$API_PORT"
[[ -n "${UI_PID:-}" ]] && echo "UI:  http://localhost:$UI_PORT"
wait

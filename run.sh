#!/usr/bin/env bash
# WriteUP — run backend (FastAPI :8000) and frontend (Vite :5173) together.
set -euo pipefail
cd "$(dirname "$0")"

.venv/bin/python backend/run.py &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT

(cd frontend && npm run dev)

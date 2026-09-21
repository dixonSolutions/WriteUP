#!/usr/bin/env bash
# WriteUP — one-shot setup: backend venv + deps, frontend deps, fonts, demo data.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Python backend"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r backend/requirements.txt

echo "==> Handwriting fonts (OFL, from google/fonts)"
.venv/bin/python scripts/fetch_fonts.py

echo "==> Frontend"
(cd frontend && npm install)

echo "==> Handwriting samples (for style learning)"
.venv/bin/python scripts/make_samples.py

echo
echo "Setup complete. Run the app with:  ./run.sh"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Creating default .env from template..."
  cp "${ROOT_DIR}/.env.example" "${ENV_FILE}"
fi

echo "Setting up virtual environment..."
make -C "${ROOT_DIR}" setup

echo "Applying database bootstrap (placeholder)..."
"${ROOT_DIR}/.venv/bin/python" voice_ai_keep_gepa/scripts/init_db.py

echo "Bootstrap complete."

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
export NVM_DIR="${HOME}/.nvm"

if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  . "${NVM_DIR}/nvm.sh"
  nvm use 22 >/dev/null
fi

echo "[1/2] starting backend on http://127.0.0.1:8000"
(
  cd "${ROOT_DIR}"
  python3 scripts/run_evaluation_api.py
) &

BACKEND_PID=$!
trap 'kill ${BACKEND_PID} >/dev/null 2>&1 || true' EXIT

echo "[2/2] starting frontend on http://127.0.0.1:5173"
cd "${ROOT_DIR}/frontend"
if [[ ! -f "node_modules/vite/bin/vite.js" ]]; then
  echo "frontend dependencies missing, running npm install"
  npm install --no-fund --no-audit
fi
npm run dev -- --host 127.0.0.1 --port 5173

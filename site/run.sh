#!/usr/bin/env bash
# Demo console on http://127.0.0.1:8765 . Loads demo/.env and runs under EDOT, so the CLI-style spans reach the Observability project.
#   site/run.sh            # live + practice
#   PORT=8000 site/run.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../demo"
set -a; source .env; set +a
export OTEL_SERVICE_NAME="${OTEL_SERVICE_NAME:-apex-rag-demo}"
PATH="$PWD/.venv/bin:$PATH"
exec opentelemetry-instrument python -m uvicorn app:app --app-dir "$HERE" --host 127.0.0.1 --port "${PORT:-8765}" --log-level warning

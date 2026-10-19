#!/usr/bin/env bash
# Loads .env into the environment (OTel reads env vars at startup) and runs the demo under EDOT.
#   ./run.sh retrieve Q01
#   ./run.sh compare Q06
set -euo pipefail
cd "$(dirname "$0")"
set -a; source .env; set +a
exec opentelemetry-instrument python apex_demo.py "$@"

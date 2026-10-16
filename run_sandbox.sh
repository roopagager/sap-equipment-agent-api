#!/usr/bin/env bash
# Run the SAP Equipment Agent API against the real SAP sandbox (macOS / Linux).
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
if [ -z "${SAP_API_KEY:-}" ]; then read -rsp "Paste your SAP API key: " SAP_API_KEY; echo; fi
export SAP_API_KEY SAP_MODE=sandbox
echo "Open http://localhost:8000/equipment/10001883  (Ctrl+C to stop)"
python -m uvicorn app.main:app --port 8000

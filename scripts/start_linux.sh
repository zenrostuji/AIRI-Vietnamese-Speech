#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
exec .venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port 23333

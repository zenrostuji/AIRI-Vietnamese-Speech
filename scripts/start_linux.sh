#!/usr/bin/env bash
# Launch AIRI Vietnamese Speech on Linux Mint / Ubuntu.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/airi-vietnamese-speech"
VENV_DIR="$RUNTIME_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required. Install python3 and python3-venv, then run again." >&2
  exit 1
fi

mkdir -p "$RUNTIME_DIR"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

if ! "$VENV_DIR/bin/python" -c 'import fastapi, faster_whisper, uvicorn, vieneu, webview' >/dev/null 2>&1; then
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"
fi
if ! "$VENV_DIR/bin/python" -c 'import torch, torchaudio' >/dev/null 2>&1; then
  echo "Installing the CPU runtime required for voice cloning (one-time download)..."
  "$VENV_DIR/bin/python" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

exec "$VENV_DIR/bin/python" "$ROOT_DIR/launcher.py"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

MW_AGENT="${MW_AGENT:-miniagent_like}"
MW_PROVIDER="${MW_PROVIDER:-minimax}"
MW_MODEL="${MW_MODEL:-MiniMax-M2.5}"
MW_WORKSPACE="${MW_WORKSPACE:-$ROOT_DIR}"
MW_SESSION="${MW_SESSION:-default}"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install -e "$ROOT_DIR" >/dev/null

exec "$VENV_DIR/bin/python" -m mini_worker.cli chat \
  --agent "$MW_AGENT" \
  --provider "$MW_PROVIDER" \
  --model "$MW_MODEL" \
  --workspace "$MW_WORKSPACE" \
  --session "$MW_SESSION" \
  "$@"

#!/usr/bin/env bash
# Bootstrap the blackrim-knowledge-graph pack's self-contained venv (idempotent).
#
# Installs the engine (the repository one level up) in editable mode so `kg` and
# `python -m blackrim_kg` resolve under the pack's own interpreter. The engine
# spine is pure standard library; the optional `algorithms` (networkx) and `ast`
# (tree-sitter) extras are NOT installed here — the spine and the ast-lens
# adapter do not need them. Install them explicitly if you build the analysis or
# supplemental-AST layers:  .venv/bin/pip install -e "<repo>[algorithms,ast]"
set -euo pipefail
PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PACK_DIR/.." && pwd)"
PY="${PYTHON:-python3}"
"$PY" -m venv "$PACK_DIR/.venv"
"$PACK_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$PACK_DIR/.venv/bin/pip" install --quiet -e "$REPO_ROOT"
echo "blackrim-knowledge-graph venv ready: $PACK_DIR/.venv"

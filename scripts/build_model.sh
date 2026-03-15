#!/usr/bin/env bash
# build_model.sh — Build an Ollama model from a Modelfile
# Usage: ./scripts/build_model.sh [model-name] [modelfile-path]
set -euo pipefail

MODEL_NAME="${1:-toolsmith}"
MODEL_FILE="${2:-ollama/Modelfile}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Model Forge: Build ==="
echo "Model:     $MODEL_NAME"
echo "Modelfile: $MODEL_FILE"

# Resolve path
if [[ ! "$MODEL_FILE" = /* ]]; then
    MODEL_FILE="$ROOT/$MODEL_FILE"
fi

if [[ ! -f "$MODEL_FILE" ]]; then
    echo "ERROR: Modelfile not found at $MODEL_FILE" >&2
    exit 1
fi

# Check Ollama
if ! curl -sf http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "ERROR: Ollama is not running." >&2
    exit 1
fi
echo "Ollama: $(curl -sf http://localhost:11434/api/version | python3 -c 'import sys,json; print(json.load(sys.stdin)["version"])')"

# Build
echo ""
echo "Building model..."
ollama create "$MODEL_NAME" -f "$MODEL_FILE"

# Verify
echo ""
echo "Verifying..."
ollama show "$MODEL_NAME" --modelfile | head -5

# Quick test
echo ""
echo "Quick generation test..."
RESPONSE=$(curl -sf http://localhost:11434/api/generate -d "{\"model\":\"$MODEL_NAME\",\"prompt\":\"Say hello.\",\"stream\":false}" 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("response","(no response)")[:200])') || true
echo "Response: $RESPONSE"

echo ""
echo "=== Build complete: $MODEL_NAME ==="

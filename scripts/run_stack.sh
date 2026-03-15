#!/usr/bin/env bash
# run_stack.sh — Check and start the Model Forge stack
# Usage: ./scripts/run_stack.sh [model-name]
set -uo pipefail

MODEL_NAME="${1:-toolsmith}"

echo "=== Model Forge: Run Stack ==="

# Ollama
echo "1. Checking Ollama..."
if curl -sf http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "   Ollama running"
else
    echo "   Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
fi

# Model
echo "2. Checking model '$MODEL_NAME'..."
if ollama list 2>/dev/null | grep -q "$MODEL_NAME"; then
    echo "   Model found"
else
    echo "   Building model..."
    bash "$(dirname "$0")/build_model.sh" "$MODEL_NAME"
fi

# Open WebUI
echo "3. Checking Open WebUI..."
if curl -sf http://localhost:3010/ > /dev/null 2>&1 || curl -sI http://localhost:3010/ 2>/dev/null | grep -q "307\|302"; then
    echo "   Open WebUI at http://localhost:3010"
else
    echo "   Open WebUI not reachable"
fi

# MCPO
echo "4. Checking MCPO..."
if curl -sf http://localhost:8800/openapi.json > /dev/null 2>&1; then
    echo "   MCPO at http://localhost:8800"
else
    echo "   MCPO not reachable"
fi

echo ""
echo "=== Stack Ready ==="
echo "Open WebUI: http://localhost:3010"
echo "Model:      $MODEL_NAME"

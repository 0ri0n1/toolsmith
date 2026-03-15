#!/usr/bin/env bash
# test_stack.sh — Run smoke tests
# Usage: ./scripts/test_stack.sh [model-name]
set -uo pipefail

MODEL_NAME="${1:-toolsmith}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Model Forge: Test Stack ==="
echo "Model: $MODEL_NAME"

echo ""
echo "--- Smoke Tests ---"
python3 "$ROOT/tests/tool_smoke_test.py" --model "$MODEL_NAME"
SMOKE=$?

echo ""
if [ $SMOKE -eq 0 ]; then
    echo "Smoke tests: PASSED"
else
    echo "Smoke tests: FAILED"
fi

exit $SMOKE

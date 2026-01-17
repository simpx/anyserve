#!/bin/bash
# AnyServe LlamaCpp Example - Run Client
# Tests the LlamaCpp server via OpenAI-compatible API

set -e

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Activate venv if it exists
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT/python:$PROJECT_ROOT:$PYTHONPATH"

OPENAI_URL="${OPENAI_URL:-http://localhost:8080}"

echo "Running LlamaCpp client..."
echo "Server URL: $OPENAI_URL"
echo ""

python3 examples/llamacpp/client.py --url "$OPENAI_URL" "$@"

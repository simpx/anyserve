#!/bin/bash
# AnyServe LlamaCpp Example - Start Server
# Starts AnyServe with embedded OpenAI-compatible API server

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

# Default model path (can be overridden via environment variable)
MODEL_PATH="${ANYSERVE_MODEL_PATH:-$HOME/.cache/modelscope/hub/models/Qwen/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf}"
MODEL_NAME="${ANYSERVE_MODEL_NAME:-qwen3-0.6b}"
ANYSERVE_PORT="${ANYSERVE_PORT:-8000}"
OPENAI_PORT="${OPENAI_PORT:-8080}"

# Check if model exists
if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: Model file not found: $MODEL_PATH"
    echo ""
    echo "Please set ANYSERVE_MODEL_PATH to your GGUF model file path:"
    echo "  export ANYSERVE_MODEL_PATH=/path/to/your/model.gguf"
    echo "  ./run_server.sh"
    exit 1
fi

echo "=============================================="
echo "AnyServe LlamaCpp Server"
echo "=============================================="
echo "Model: $MODEL_PATH"
echo "Model Name: $MODEL_NAME"
echo "KServe gRPC port: $ANYSERVE_PORT"
echo "OpenAI API port: $OPENAI_PORT"
echo "=============================================="
echo ""

# Start AnyServe with embedded OpenAI server
anyserve serve "$MODEL_PATH" \
    --name "$MODEL_NAME" \
    --port "$ANYSERVE_PORT" \
    --openai-port "$OPENAI_PORT"

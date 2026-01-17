#!/bin/bash
# AnyServe LlamaCpp Example - Start Server
# Starts both AnyServe (gRPC backend) and OpenAI-compatible API server

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
echo "AnyServe gRPC port: $ANYSERVE_PORT"
echo "OpenAI API port: $OPENAI_PORT"
echo "=============================================="
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down servers..."
    if [ ! -z "$ANYSERVE_PID" ]; then
        kill $ANYSERVE_PID 2>/dev/null || true
        wait $ANYSERVE_PID 2>/dev/null || true
    fi
    echo "Done."
}

trap cleanup EXIT INT TERM

# Start AnyServe in background
echo "Starting AnyServe backend..."
anyserve serve "$MODEL_PATH" --name "$MODEL_NAME" --port "$ANYSERVE_PORT" &
ANYSERVE_PID=$!

# Wait for AnyServe to be ready
echo "Waiting for AnyServe to start..."
sleep 3

# Check if AnyServe is still running
if ! kill -0 $ANYSERVE_PID 2>/dev/null; then
    echo "Error: AnyServe failed to start"
    exit 1
fi

echo "AnyServe started (PID: $ANYSERVE_PID)"
echo ""

# Start OpenAI-compatible server in foreground
echo "Starting OpenAI-compatible API server..."
echo ""
python3 -m openai_server --anyserve-endpoint "localhost:$ANYSERVE_PORT" --port "$OPENAI_PORT"

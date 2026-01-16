#!/bin/bash
#
# Streaming Example - Start Server
#
# This script starts the streaming server on port 8000 (gRPC streaming on port 9100).
#
# Usage:
#   ./examples/streaming/run_server.sh
#
# Then run the test client in another terminal:
#   ./examples/streaming/run_client.sh

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Activate venv if it exists
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT/python:$PROJECT_ROOT:$PYTHONPATH"

echo "=== AnyServe Streaming Example ==="
echo ""
echo "Starting streaming server..."
echo "  HTTP port: 8000"
echo "  gRPC streaming port: 9100"
echo ""

python3 examples/streaming/app.py

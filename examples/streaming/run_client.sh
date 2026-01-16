#!/bin/bash
#
# Streaming Example - Run Client
#
# Prerequisites:
#   Start the server first: ./examples/streaming/run_server.sh
#
# Usage:
#   ./examples/streaming/run_client.sh [port]
#
# Arguments:
#   port - gRPC streaming port (default: 9100)

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

echo "Running streaming test client..."
echo ""

python3 examples/streaming/test_client.py "$@"

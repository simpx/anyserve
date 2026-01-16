#!/bin/bash
#
# Pipeline Example - Run Client
#
# Prerequisites:
#   Start the servers first: ./examples/pipeline/run_server.sh
#
# Usage:
#   ./examples/pipeline/run_client.sh

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

echo "Running pipeline test client..."
echo ""

python3 examples/pipeline/test_client.py "$@"

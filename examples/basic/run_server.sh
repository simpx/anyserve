#!/bin/bash
# AnyServe Basic Example - Start Server (Production Mode)
# Uses anyserve.cli for production deployment

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

echo "Starting AnyServe server (production mode)..."
echo "Models: echo, add, classifier:v1"
echo "Port: 8000"
echo ""

python3 -m anyserve.cli examples.basic.app:app --port 8000 --workers 1

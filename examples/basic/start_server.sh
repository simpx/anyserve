#!/bin/bash
# AnyServe Basic Example - Start Server (Production Mode)
# Uses anyserve.cli for production deployment

set -e

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "Starting AnyServe server (production mode)..."
echo "Models: echo, add, classifier:v1"
echo "Port: 8000"
echo ""

python -m anyserve.cli examples.basic.app:app --port 8000 --workers 1

#!/bin/bash
# AnyServe Basic Example - Start Server (Development Mode)
# Runs the basic example using direct Python execution (dev mode)
# This demonstrates that basic_dev is just basic in development mode

set -e

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "Starting AnyServe server (development mode)..."
echo "Using: examples/basic/app.py"
echo "Models: echo, add, classifier:v1"
echo "Port: 8000"
echo ""

python examples/basic/app.py

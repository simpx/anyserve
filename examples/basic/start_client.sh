#!/bin/bash
# AnyServe Basic Example - Start Client
# Tests the basic example models

set -e

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "Running test client..."
echo ""

python examples/basic/test_client.py "$@"

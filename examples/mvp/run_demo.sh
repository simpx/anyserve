#!/bin/bash
set -e

# Cleanup
rm -rf tmp_mvp

# Set Python Path to include source
export PYTHONPATH=$PYTHONPATH:$(pwd)/python:$(pwd)

echo "=== MVP Demo: Capability-based Routing with Delegation ==="
echo ""
echo "Starting Replica H1 (decode.heavy capability)..."
~/.local/bin/uv run python examples/mvp/replica_h1.py 2>&1 &
PID_H1=$!
echo "Replica H1 PID: $PID_H1"

sleep 1

echo "Starting Replica S1 (decode capability, delegates to decode.heavy)..."
~/.local/bin/uv run python examples/mvp/replica_s1.py 2>&1 &
PID_S1=$!
echo "Replica S1 PID: $PID_S1"

sleep 2

echo ""
echo "Running Client..."
echo ""
~/.local/bin/uv run python examples/mvp/client.py

echo ""
echo "=== Stopping Replicas ==="
kill $PID_S1 $PID_H1 2>/dev/null || true

echo ""
echo "=== Demo Complete ==="

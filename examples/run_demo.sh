#!/bin/bash
set -e

# Cleanup
rm -rf tmp_distributed

# Set Python Path to include source and current dir (for shared module)
export PYTHONPATH=$PYTHONPATH:$(pwd)/python:$(pwd)

echo "--- Starting Node Step2 ---"
uv run python examples/node_step2.py > node2.log 2>&1 &
PID2=$!
echo "Node Step2 PID: $PID2"

echo "--- Starting Node Step1 ---"
uv run python examples/node_step1.py > node1.log 2>&1 &
PID1=$!
echo "Node Step1 PID: $PID1"

sleep 3

echo "--- Running Client ---"
uv run python examples/client.py

echo "--- Stopping Nodes ---"
kill $PID1 $PID2
echo "Done."

echo "--- Node 1 Log ---"
cat node1.log
echo "--- Node 2 Log ---"
cat node2.log

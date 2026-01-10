#!/bin/bash
# anyServe MVP Step 1 Demo
# This script demonstrates the core anyServe functionality:
# 1. Local Hit: Client -> Node A ("small") -> Success
# 2. Delegation: Client -> Node A ("large") -> Scheduler lookup -> Node B -> Success

set -e

# Configuration
DATA_DIR="/tmp/anyserve_data"
SCHEDULER_PORT=8000
NODE_A_PORT=50051
NODE_B_PORT=50052

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_DIR"

echo "=== anyServe MVP Step 1 Demo ==="
echo "Project dir: $PROJECT_DIR"

# Cleanup
echo ""
echo "=== Cleanup ==="
rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR"
echo "Created data directory: $DATA_DIR"

# Kill any existing processes
pkill -f "anyserve_scheduler" 2>/dev/null || true
pkill -f "anyserve-node" 2>/dev/null || true
sleep 1

# Export environment
export PYTHONPATH="$PROJECT_DIR"
export ANYSERVE_DATA_DIR="$DATA_DIR"
export PYTHON_PATH="$(which python)"

# Start Scheduler
echo ""
echo "=== Starting Scheduler (port $SCHEDULER_PORT) ==="
~/.local/bin/uv run python -c "from anyserve_scheduler import run; run(port=$SCHEDULER_PORT)" &
SCHEDULER_PID=$!
sleep 2
echo "Scheduler started (PID: $SCHEDULER_PID)"

# Start Node A
echo ""
echo "=== Starting Node A (port $NODE_A_PORT, cap: small) ==="
"$PROJECT_DIR/target/debug/anyserve-node" node-a $NODE_A_PORT small "http://127.0.0.1:$SCHEDULER_PORT" &
NODE_A_PID=$!
sleep 3
echo "Node A started (PID: $NODE_A_PID)"

# Start Node B
echo ""
echo "=== Starting Node B (port $NODE_B_PORT, cap: large) ==="
"$PROJECT_DIR/target/debug/anyserve-node" node-b $NODE_B_PORT large "http://127.0.0.1:$SCHEDULER_PORT" &
NODE_B_PID=$!
sleep 3
echo "Node B started (PID: $NODE_B_PID)"

# Generate gRPC stubs
echo ""
echo "=== Generating gRPC stubs ==="
~/.local/bin/uv run python -m grpc_tools.protoc \
    -I"$PROJECT_DIR/proto" \
    --python_out="$PROJECT_DIR/examples/step1" \
    --grpc_python_out="$PROJECT_DIR/examples/step1" \
    "$PROJECT_DIR/proto/anyserve.proto"
echo "gRPC stubs generated"

# Run client tests
echo ""
echo "=== Running Client Tests ==="
~/.local/bin/uv run python "$PROJECT_DIR/examples/step1/client.py"

# Cleanup
echo ""
echo "=== Stopping processes ==="
kill $NODE_A_PID $NODE_B_PID $SCHEDULER_PID 2>/dev/null || true
echo "All processes stopped."
echo ""
echo "=== Demo Complete ==="

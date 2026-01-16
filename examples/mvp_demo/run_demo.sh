#!/bin/bash
# MVP Demo Script
# This script demonstrates the AnyServe MVP architecture

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_SERVER_PORT=8080
REPLICA_A_PORT=50051  # Chat capability
REPLICA_B_PORT=50052  # Embed capability
REPLICA_C_PORT=50053  # Heavy capability
OBJECT_STORE="/tmp/anyserve-objects"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"

    # Kill all background processes
    if [ ! -z "$API_SERVER_PID" ]; then
        kill $API_SERVER_PID 2>/dev/null || true
    fi
    if [ ! -z "$REPLICA_A_PID" ]; then
        kill $REPLICA_A_PID 2>/dev/null || true
    fi
    if [ ! -z "$REPLICA_B_PID" ]; then
        kill $REPLICA_B_PID 2>/dev/null || true
    fi
    if [ ! -z "$REPLICA_C_PID" ]; then
        kill $REPLICA_C_PID 2>/dev/null || true
    fi

    # Kill any remaining processes on our ports
    lsof -ti:$API_SERVER_PORT | xargs kill 2>/dev/null || true
    lsof -ti:$REPLICA_A_PORT | xargs kill 2>/dev/null || true
    lsof -ti:$REPLICA_B_PORT | xargs kill 2>/dev/null || true
    lsof -ti:$REPLICA_C_PORT | xargs kill 2>/dev/null || true

    echo -e "${GREEN}Cleanup complete${NC}"
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Print header
echo -e "${BLUE}"
echo "============================================================"
echo "           AnyServe MVP Demo"
echo "============================================================"
echo -e "${NC}"

# Create object store directory
echo -e "${YELLOW}Creating object store directory: $OBJECT_STORE${NC}"
mkdir -p $OBJECT_STORE

# Change to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${YELLOW}Working directory: $(pwd)${NC}"
echo ""

# Step 1: Start API Server
echo -e "${GREEN}Step 1: Starting API Server on port $API_SERVER_PORT${NC}"
python api_server/main.py --port $API_SERVER_PORT &
API_SERVER_PID=$!
echo "API Server PID: $API_SERVER_PID"
sleep 2

# Check if API Server is running
if ! kill -0 $API_SERVER_PID 2>/dev/null; then
    echo -e "${RED}ERROR: API Server failed to start${NC}"
    exit 1
fi
echo -e "${GREEN}API Server started successfully${NC}"
echo ""

# Step 2: Start Replica A (Chat capability)
echo -e "${GREEN}Step 2: Starting Replica A (Chat) on port $REPLICA_A_PORT${NC}"
# Note: In MVP mode without C++ ingress, we run the worker directly
python -m anyserve.worker \
    --app examples.mvp_demo.chat_app:app \
    --ingress localhost:9051 \
    --worker-id worker-chat \
    --api-server http://localhost:$API_SERVER_PORT \
    --object-store $OBJECT_STORE \
    --replica-id replica-chat &
REPLICA_A_PID=$!
echo "Replica A PID: $REPLICA_A_PID"
sleep 1
echo ""

# Step 3: Start Replica B (Embed capability)
echo -e "${GREEN}Step 3: Starting Replica B (Embed) on port $REPLICA_B_PORT${NC}"
python -m anyserve.worker \
    --app examples.mvp_demo.embed_app:app \
    --ingress localhost:9052 \
    --worker-id worker-embed \
    --api-server http://localhost:$API_SERVER_PORT \
    --object-store $OBJECT_STORE \
    --replica-id replica-embed &
REPLICA_B_PID=$!
echo "Replica B PID: $REPLICA_B_PID"
sleep 1
echo ""

# Step 4: Start Replica C (Heavy capability)
echo -e "${GREEN}Step 4: Starting Replica C (Heavy) on port $REPLICA_C_PORT${NC}"
python -m anyserve.worker \
    --app examples.mvp_demo.heavy_app:app \
    --ingress localhost:9053 \
    --worker-id worker-heavy \
    --api-server http://localhost:$API_SERVER_PORT \
    --object-store $OBJECT_STORE \
    --replica-id replica-heavy &
REPLICA_C_PID=$!
echo "Replica C PID: $REPLICA_C_PID"
sleep 2
echo ""

# Print status
echo -e "${BLUE}"
echo "============================================================"
echo "           MVP Demo Started"
echo "============================================================"
echo -e "${NC}"
echo "API Server:  http://localhost:$API_SERVER_PORT"
echo "Replica A:   Chat capability   (replica-chat)"
echo "Replica B:   Embed capability  (replica-embed)"
echo "Replica C:   Heavy capability  (replica-heavy)"
echo ""
echo "Object Store: $OBJECT_STORE"
echo ""

# Show registry
echo -e "${YELLOW}Current Registry:${NC}"
curl -s http://localhost:$API_SERVER_PORT/registry | python -m json.tool 2>/dev/null || echo "(waiting for registration...)"
echo ""

echo -e "${BLUE}"
echo "============================================================"
echo "           Test Commands"
echo "============================================================"
echo -e "${NC}"
echo "# Check registry:"
echo "curl http://localhost:$API_SERVER_PORT/registry | python -m json.tool"
echo ""
echo "# Test chat capability:"
echo "curl -X POST http://localhost:$API_SERVER_PORT/infer/json \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'X-Capability-Type: chat' \\"
echo "  -d '{\"inputs\": [{\"name\": \"text\", \"datatype\": \"BYTES\", \"shape\": [1], \"contents\": {\"bytes_contents\": [\"Hello World\"]}}]}'"
echo ""
echo "# Test embed capability:"
echo "curl -X POST http://localhost:$API_SERVER_PORT/infer/json \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'X-Capability-Type: embed' \\"
echo "  -d '{\"inputs\": [{\"name\": \"text\", \"datatype\": \"BYTES\", \"shape\": [1], \"contents\": {\"bytes_contents\": [\"Sample text\"]}}]}'"
echo ""
echo "# Test heavy capability:"
echo "curl -X POST http://localhost:$API_SERVER_PORT/infer/json \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'X-Capability-Type: heavy' \\"
echo "  -d '{\"inputs\": [{\"name\": \"data\", \"datatype\": \"BYTES\", \"shape\": [1], \"contents\": {\"bytes_contents\": [\"Heavy task data\"]}}]}'"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for user to stop
wait

#!/bin/bash
#
# Multi-Server Example - Start Servers
#
# This script starts:
# 1. API Server on port 8080
# 2. Worker 1 (multiply) on port 50051
# 3. Worker 2 (divide, power) on port 50052
#
# Usage:
#   ./examples/multi_server/run_server.sh
#
# Then run the test client in another terminal:
#   ./examples/multi_server/run_client.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${GREEN}=== AnyServe Multi-Server Example ===${NC}"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down all processes...${NC}"

    # Kill all background jobs
    jobs -p | xargs -r kill 2>/dev/null || true

    # Wait for processes to terminate
    wait 2>/dev/null || true

    echo -e "${GREEN}All processes stopped.${NC}"
}

# Set trap for cleanup on exit
trap cleanup EXIT INT TERM

# Change to project root
cd "$PROJECT_ROOT"

# Activate venv if it exists
if [ -d "$PROJECT_ROOT/.venv" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Set PYTHONPATH to include the python directory
export PYTHONPATH="$PROJECT_ROOT/python:$PROJECT_ROOT:$PYTHONPATH"

# Clean up any stale processes on our ports
echo -e "${YELLOW}Cleaning up stale processes...${NC}"
pkill -f "anyserve.cli.*--port 50051" 2>/dev/null || true
pkill -f "anyserve.cli.*--port 50052" 2>/dev/null || true
pkill -f "anyserve_dispatcher.*--port 50051" 2>/dev/null || true
pkill -f "anyserve_dispatcher.*--port 50052" 2>/dev/null || true
# Also kill any processes holding these ports
lsof -ti :50051 | xargs kill -9 2>/dev/null || true
lsof -ti :50052 | xargs kill -9 2>/dev/null || true
lsof -ti :51051 | xargs kill -9 2>/dev/null || true
lsof -ti :51052 | xargs kill -9 2>/dev/null || true
sleep 1

# 1. Start API Server
echo -e "${GREEN}[1/3] Starting API Server on port 8080...${NC}"
python3 api_server/main.py --port 8080 &
API_SERVER_PID=$!
sleep 2

# Check if API Server started
if ! kill -0 $API_SERVER_PID 2>/dev/null; then
    echo -e "${RED}ERROR: API Server failed to start${NC}"
    exit 1
fi
echo -e "${GREEN}      API Server started (PID: $API_SERVER_PID)${NC}"

# 2. Start Worker 1 (multiply)
echo -e "${GREEN}[2/3] Starting Worker 1 (multiply) on port 50051...${NC}"
python3 -m anyserve.cli examples.multi_server.worker1:app --port 50051 --api-server http://localhost:8080 --replica-id worker1 &
WORKER1_PID=$!
sleep 5

# Wait for worker to be ready
echo -e "${GREEN}      Waiting for Worker 1 to initialize...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:8080/registry | grep -q "worker1"; then
        break
    fi
    sleep 1
done
echo -e "${GREEN}      Worker 1 started (PID: $WORKER1_PID)${NC}"

# 3. Start Worker 2 (divide, power)
echo -e "${GREEN}[3/3] Starting Worker 2 (divide, power) on port 50052...${NC}"
python3 -m anyserve.cli examples.multi_server.worker2:app --port 50052 --api-server http://localhost:8080 --replica-id worker2 &
WORKER2_PID=$!
sleep 5

# Wait for worker to be ready
echo -e "${GREEN}      Waiting for Worker 2 to initialize...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:8080/registry | grep -q "worker2"; then
        break
    fi
    sleep 1
done
echo -e "${GREEN}      Worker 2 started (PID: $WORKER2_PID)${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}All services started successfully!${NC}"
echo ""
echo -e "API Server:  http://localhost:8080"
echo -e "Worker 1:    localhost:50051 (multiply)"
echo -e "Worker 2:    localhost:50052 (divide, power)"
echo ""
echo -e "View registry: ${YELLOW}curl http://localhost:8080/registry | jq${NC}"
echo ""
echo -e "Run test client: ${YELLOW}./examples/multi_server/run_client.sh${NC}"
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "Press Ctrl+C to stop all services"
echo ""

# Wait for all processes
wait

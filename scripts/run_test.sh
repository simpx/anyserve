#!/bin/bash
set -e
export PYTHON_PATH=/Users/siqian/workspace/anyserve/.venv/bin/python3
~/.cargo/bin/cargo run -- 9000 > server.log 2>&1 &
PID=$!
echo "Server PID: $PID"
sleep 10
echo "--- Server Log ---"
cat server.log
echo "--- Running Client ---"
uv run python examples/test_kserve.py || echo "Client failed"
kill $PID

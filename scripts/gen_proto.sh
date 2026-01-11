#!/bin/bash
set -e

# Generate Python gRPC code for the worker
echo "Generating Python gRPC code..."
uv run python -m grpc_tools.protoc \
    -Iproto \
    --python_out=anyserve_worker/proto \
    --grpc_python_out=anyserve_worker/proto \
    proto/grpc_predict_v2.proto

# Ensure __init__.py exists in output dir
touch anyserve_worker/proto/__init__.py

echo "Done."

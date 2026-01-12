# Justfile for anyserve POC

# Default Python path for development
export PYTHONPATH := "python:$PYTHONPATH"

# List available commands
default:
    @just --list

# Setup environment (install dependencies)
setup:
    uv sync

# Install C++ dependencies via Conan
setup-cpp:
    cd cpp && conan install . --output-folder=build --build=missing -s build_type=Release

# Generate proto files using Conan's protoc (version-matched)
gen-proto-cpp:
    #!/usr/bin/env bash
    set -e
    cd cpp
    CONAN_PROTOC=$(find ~/.conan2 -name "protoc-27*" -type f 2>/dev/null | head -1)
    GRPC_PLUGIN=$(find ~/.conan2 -name "grpc_cpp_plugin" -type f 2>/dev/null | head -1)
    if [ -z "$CONAN_PROTOC" ]; then echo "Error: protoc not found in Conan"; exit 1; fi
    if [ -z "$GRPC_PLUGIN" ]; then echo "Error: grpc_cpp_plugin not found in Conan"; exit 1; fi
    echo "Using protoc: $CONAN_PROTOC"
    echo "Using grpc_plugin: $GRPC_PLUGIN"
    rm -rf generated && mkdir -p generated
    $CONAN_PROTOC --cpp_out=generated --grpc_out=generated --plugin=protoc-gen-grpc="$GRPC_PLUGIN" -I../proto ../proto/grpc_predict_v2.proto
    echo "Proto files generated in cpp/generated/"

# Build C++ extension and install in development mode
build:
    cd cpp && cmake -B build -S . -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=build/conan_toolchain.cmake -DBUILD_PYTHON_EXTENSION=ON -DREGENERATE_PROTO=OFF
    cd cpp && cmake --build build --parallel
    cp cpp/build/_core*.so python/anyserve/ 2>/dev/null || cp cpp/build/_core*.dylib python/anyserve/ 2>/dev/null || true

# Build standalone executable only
build-node:
    cd cpp && cmake -B build -S . -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=build/conan_toolchain.cmake -DBUILD_PYTHON_EXTENSION=OFF -DREGENERATE_PROTO=OFF
    cd cpp && cmake --build build --parallel --target anyserve_node

# Run the API server
run: build
    uv run uvicorn anyserve.main:app --reload

# Run anyserve node with app target
run-node target: build-node
    cpp/build/anyserve_node {{target}}

# Test C++ core
test-cpp:
    PYTHONPATH="python:$PYTHONPATH" python3 tests/python/test_cpp_core.py

# Clean build artifacts
clean:
    rm -rf cpp/build
    rm -rf python/anyserve/_core*.so python/anyserve/_core*.dylib

# Run tests
test:
    PYTHONPATH="python" uv run pytest tests/

# Generate proto files (Python)
gen-proto:
    ./scripts/gen_proto.sh

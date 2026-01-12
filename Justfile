default:
    @just --list

setup:
    #!/usr/bin/env bash
    set -e
    uv venv
    pushd cpp && conan install . --output-folder=build --build=missing -s build_type=Release && popd

build:
    #!/usr/bin/env bash
    set -e
    # Generate Python protobuf files (for kserve.py and worker)
    mkdir -p python/anyserve/_proto python/anyserve/worker/proto
    uv run python -m grpc_tools.protoc -I proto \
        --python_out=python/anyserve/_proto \
        --grpc_python_out=python/anyserve/_proto \
        proto/grpc_predict_v2.proto proto/worker_management.proto
    touch python/anyserve/_proto/__init__.py
    # Also generate for worker.client module
    uv run python -m grpc_tools.protoc -I proto \
        --python_out=python/anyserve/worker/proto \
        --grpc_python_out=python/anyserve/worker/proto \
        proto/grpc_predict_v2.proto proto/worker_management.proto
    # Fix imports in generated grpc files
    sed -i '' 's/^import grpc_predict_v2_pb2/from . import grpc_predict_v2_pb2/' python/anyserve/worker/proto/grpc_predict_v2_pb2_grpc.py
    sed -i '' 's/^import worker_management_pb2/from . import worker_management_pb2/' python/anyserve/worker/proto/worker_management_pb2_grpc.py
    touch python/anyserve/worker/proto/__init__.py
    # Build C++ Dispatcher
    cd cpp/build
    rm -f CMakeCache.txt
    cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake
    cmake --build .
    cd ../..
    # Install Python package
    uv pip install -e . -v

test target="all":
    #!/usr/bin/env bash
    set -e
    case "{{target}}" in
        cpp)
            uv run python tests/python/test_cpp_core.py
            ;;
        all)
            uv run python tests/python/test_cpp_core.py
            ;;
        *)
            echo "Usage: just test [cpp|all]"
            exit 1
            ;;
    esac

clean:
    rm -rf cpp/build
    rm -rf python/anyserve/_core*.so python/anyserve/_core*.dylib
    rm -rf python/anyserve/_proto
    rm -rf python/anyserve/worker/proto
    rm -rf .pytest_cache
    uv pip uninstall anyserve 2>/dev/null || true
    find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true

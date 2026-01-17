default:
    @just --list

setup python="":
    #!/usr/bin/env bash
    set -e
    if [ -n "{{python}}" ]; then
        uv venv --python {{python}}
    else
        uv venv
    fi
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
    # Fix imports in _proto/
    sed -i '' 's/^import grpc_predict_v2_pb2/from . import grpc_predict_v2_pb2/' python/anyserve/_proto/grpc_predict_v2_pb2_grpc.py
    sed -i '' 's/^import worker_management_pb2/from . import worker_management_pb2/' python/anyserve/_proto/worker_management_pb2_grpc.py
    # Also generate for worker.client module
    uv run python -m grpc_tools.protoc -I proto \
        --python_out=python/anyserve/worker/proto \
        --grpc_python_out=python/anyserve/worker/proto \
        proto/grpc_predict_v2.proto proto/worker_management.proto
    touch python/anyserve/worker/proto/__init__.py
    # Fix imports in worker/proto/
    sed -i '' 's/^import grpc_predict_v2_pb2/from . import grpc_predict_v2_pb2/' python/anyserve/worker/proto/grpc_predict_v2_pb2_grpc.py
    sed -i '' 's/^import worker_management_pb2/from . import worker_management_pb2/' python/anyserve/worker/proto/worker_management_pb2_grpc.py
    # Build C++ Agent
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
    rm -rf dist
    uv pip uninstall anyserve 2>/dev/null || true
    find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true

# Build wheel for distribution
wheel python="":
    #!/usr/bin/env bash
    set -e
    echo "=== Building AnyServe wheel ==="
    # Detect Python version from current venv or use specified
    if [ -n "{{python}}" ]; then
        PY_VERSION="{{python}}"
    elif [ -f ".venv/bin/python" ]; then
        PY_VERSION=$(.venv/bin/python --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    else
        PY_VERSION="3.13"
    fi
    echo "Using Python $PY_VERSION"
    # Generate protobuf files
    mkdir -p python/anyserve/_proto python/anyserve/worker/proto
    uv run python -m grpc_tools.protoc -I proto \
        --python_out=python/anyserve/_proto \
        --grpc_python_out=python/anyserve/_proto \
        proto/grpc_predict_v2.proto proto/worker_management.proto
    touch python/anyserve/_proto/__init__.py
    # Fix imports in _proto/
    sed -i '' 's/^import grpc_predict_v2_pb2/from . import grpc_predict_v2_pb2/' python/anyserve/_proto/grpc_predict_v2_pb2_grpc.py
    sed -i '' 's/^import worker_management_pb2/from . import worker_management_pb2/' python/anyserve/_proto/worker_management_pb2_grpc.py
    # Generate for worker/proto
    uv run python -m grpc_tools.protoc -I proto \
        --python_out=python/anyserve/worker/proto \
        --grpc_python_out=python/anyserve/worker/proto \
        proto/grpc_predict_v2.proto proto/worker_management.proto
    touch python/anyserve/worker/proto/__init__.py
    # Fix imports in worker/proto/
    sed -i '' 's/^import grpc_predict_v2_pb2/from . import grpc_predict_v2_pb2/' python/anyserve/worker/proto/grpc_predict_v2_pb2_grpc.py
    sed -i '' 's/^import worker_management_pb2/from . import worker_management_pb2/' python/anyserve/worker/proto/worker_management_pb2_grpc.py
    # Ensure conan deps exist
    if [ ! -f "cpp/build/conan_toolchain.cmake" ]; then
        echo "Installing Conan dependencies..."
        pushd cpp && conan install . --output-folder=build --build=missing -s build_type=Release && popd
    fi
    # Build wheel with matching Python version
    CMAKE_TOOLCHAIN_FILE=$(pwd)/cpp/build/conan_toolchain.cmake uv build --wheel --python $PY_VERSION
    echo "=== Done! ==="
    ls -la dist/

# Upload to PyPI
upload target="test":
    #!/usr/bin/env bash
    set -e
    if [ ! -d "dist" ] || [ -z "$(ls -A dist/*.whl 2>/dev/null)" ]; then
        echo "Error: No wheel found. Run 'just wheel' first."
        exit 1
    fi
    uv pip install twine
    case "{{target}}" in
        test)
            echo "Uploading to TestPyPI..."
            twine upload --repository testpypi dist/*
            echo "Install: pip install -i https://test.pypi.org/simple/ anyserve"
            ;;
        prod)
            echo "Uploading to PyPI..."
            twine upload dist/*
            ;;
        *)
            echo "Usage: just upload [test|prod]"
            exit 1
            ;;
    esac

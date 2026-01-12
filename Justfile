# Justfile for anyserve

# Default Python path for development
export PYTHONPATH := "python"

# List available commands
default:
    @just --list

# Setup environment (uv + conan dependencies)
setup:
    uv sync
    cd cpp && conan install . --output-folder=build --build=missing -s build_type=Release

# Build C++ server and Python extension
build:
    cd cpp && cmake -B build -S . -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=build/conan_toolchain.cmake -DBUILD_PYTHON_EXTENSION=ON -DREGENERATE_PROTO=ON
    cd cpp && cmake --build build --parallel
    cp cpp/build/_core*.so python/anyserve/ 2>/dev/null || cp cpp/build/_core*.dylib python/anyserve/ 2>/dev/null || true

# Run tests
test target="all":
    #!/usr/bin/env bash
    set -e
    case "{{target}}" in
        python)
            PYTHONPATH="python" uv run pytest tests/python/
            ;;
        cpp)
            PYTHONPATH="python" python3 tests/python/test_cpp_core.py
            ;;
        all)
            PYTHONPATH="python" python3 tests/python/test_cpp_core.py
            PYTHONPATH="python" uv run pytest tests/python/
            ;;
        *)
            echo "Usage: just test [python|cpp|all]"
            exit 1
            ;;
    esac

# Clean all build artifacts
clean:
    rm -rf cpp/build
    rm -rf python/anyserve/_core*.so python/anyserve/_core*.dylib
    rm -rf .pytest_cache
    find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true

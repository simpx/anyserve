default:
    @just --list

setup:
    #!/usr/bin/env bash
    set -e
    uv venv --python 3.13 2>/dev/null || true
    pushd cpp && conan install . --output-folder=build --build=missing -s build_type=Release && popd
    uv pip install -e . -v

test target="all":
    #!/usr/bin/env bash
    set -e
    case "{{target}}" in
        python)
            uv run pytest tests/python/
            ;;
        cpp)
            uv run python tests/python/test_cpp_core.py
            ;;
        all)
            uv run python tests/python/test_cpp_core.py
            uv run pytest tests/python/
            ;;
        *)
            echo "Usage: just test [python|cpp|all]"
            exit 1
            ;;
    esac

clean:
    rm -rf cpp/build
    rm -rf python/anyserve/_core*.so python/anyserve/_core*.dylib
    rm -rf .pytest_cache
    uv pip uninstall anyserve 2>/dev/null || true
    find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true

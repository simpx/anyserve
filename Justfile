# Justfile for anyserve POC

# List available commands
default:
    @just --list

# Setup environment (install dependencies)
setup:
    uv sync

# Build Rust extension and install in development mode
build:
    source "$HOME/.cargo/env" && uv run maturin develop

# Run the API server
run: build
    source "$HOME/.cargo/env" && uv run uvicorn anyserve.main:app --reload

# Clean build artifacts
clean:
    source "$HOME/.cargo/env" && cargo clean
    rm -rf target

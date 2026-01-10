#!/bin/bash
set -e

echo "🚀 Bootstrapping AnyServe environment..."

# 1. Install Rust (if not found)
if ! command -v cargo &> /dev/null; then
    echo "📦 Rust not found. Installing via rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path
    source "$HOME/.cargo/env"
else
    echo "✅ Rust is already installed."
fi

# 2. Install Just (if not found)
if ! command -v just &> /dev/null; then
    echo "📦 Just not found. Installing..."
    # Try using cargo first if available (since we just ensured it is)
    # But cargo build is slow, let's try pre-built binary if on macOS/Linux
    if [[ "$OSTYPE" == "darwin"* ]] || [[ "$OSTYPE" == "linux-gnu"* ]]; then
        mkdir -p "$HOME/.cargo/bin"
        curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to "$HOME/.cargo/bin"
    else
        cargo install just
    fi
else
    echo "✅ Just is already installed."
fi

echo "🎉 Environment ready! Run 'just run' to start."

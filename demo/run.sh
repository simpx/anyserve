#!/bin/bash
cd "$(dirname "$0")"

# Ensure cargo is found
export PATH="$HOME/.cargo/bin:$PATH"

echo "Building Rust Runtime (UDS Edition)..."
# Suppress noisy build output, focus on runner
cargo build --quiet

echo "Launching..."
cargo run --quiet

# AnyServe

A hybrid Python API + Rust Runtime POC project.

## Project Structure

- **`python/anyserve/`**: FastAPI application (Control Plane).
- **`src/`**: Rust implementation (Data Plane).
- **`Cargo.toml`**: Rust dependency management.
- **`agents.md`**: Guide for AI Agents.

## Prerequisites

- Python 3.11+
- Rust (Cargo)
- `uv` (Package manager)
- `just` (Command runner, optional)

## Getting Started

1.  **Bootstrap Environment** (Installs Rust & Just if missing):
    ```bash
    ./scripts/bootstrap.sh
    ```

2.  **Install Python Dependencies**:
    ```bash
    uv sync
    ```

3.  **Run Server**:
    ```bash
    just run
    ```

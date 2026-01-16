# AnyServe Basic Example - Development Mode

This directory contains scripts to run the basic example in **development mode**.

## What is Development Mode?

Development mode runs the application directly via `python app.py` instead of using the CLI wrapper (`anyserve.cli`). This is useful for:

- Quick iteration during development
- Easier debugging with direct Python execution
- Testing changes without going through the production pipeline

## Usage

```bash
# Terminal 1: Start the server (in development mode)
./examples/basic_dev/run_server.sh

# Terminal 2: Run the client
./examples/basic_dev/run_client.sh
```

## Note

This directory intentionally contains no code - it reuses the code from `examples/basic/`. The only difference is how the server is started:

- **basic/**: Uses `python -m anyserve.cli` (production mode)
- **basic_dev/**: Uses `python app.py` directly (development mode)

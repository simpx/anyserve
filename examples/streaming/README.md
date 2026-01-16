# Streaming Example

Demonstrates streaming inference with AnyServe (Server Streaming).

## Files

- `app.py` - Server with streaming chat handler
- `test_client.py` - gRPC streaming client

## Usage

```bash
# Terminal 1: Start server
./examples/streaming/run_server.sh

# Terminal 2: Run client (connects to gRPC streaming port 9100)
./examples/streaming/run_client.sh
```

## Expected Output

```
=== Streaming Client Demo ===
Connecting to: localhost:9100

Sending streaming request...
Tokens: Hello world!

=== Streaming completed ===
```

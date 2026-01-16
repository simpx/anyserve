# Streaming Example

Demonstrates streaming inference with AnyServe (Server Streaming).

## Files

- `app.py` - Server with streaming chat handler
- `test_client.py` - gRPC streaming client

## Usage

```bash
# Terminal 1: Start server
python examples/streaming/app.py

# Terminal 2: Run client (connects to gRPC streaming port 9100)
python examples/streaming/test_client.py
```

## Expected Output

```
=== Streaming Client Demo ===
Connecting to: localhost:9100

Sending streaming request...
Tokens: Hello world!

=== Streaming completed ===
```

# Basic Example

This example demonstrates the fundamental usage of AnyServe with three simple capabilities.

## Capabilities

1. **echo** - Returns all inputs as outputs
2. **add** - Adds two INT32 tensors element-wise
3. **classifier:v1** - Versioned capability example

## Files

- [app.py](app.py) - Server application with capability handlers
- [test_client.py](test_client.py) - Test client

## Quick Start

```bash
# Terminal 1: Start server
./examples/basic/run_server.sh

# Terminal 2: Run tests
./examples/basic/run_client.sh
```

## Expected Output

```
=== AnyServe KServe Client Demo ===

Testing 'add' model...
  Result: [11, 22, 33]

Testing 'echo' model...
  Output 'output_text': [b'hello world']

Testing 'classifier' v1...
  Predicted class: [42]

=== All tests completed ===
```

## Client Usage

The test client uses **Direct Mode** to connect to the Worker:

```python
from anyserve.worker.client import Client

# Direct mode - specify Worker endpoint
client = Client(endpoint="localhost:8000")

# Inference
result = client.infer(
    model_name="add",
    inputs={"a": [1, 2, 3], "b": [10, 20, 30]}
)

client.close()
```

For multi-worker scenarios with automatic endpoint discovery, see [examples/multi_server](../multi_server/).

# Basic Example

This example demonstrates the fundamental usage of AnyServe with three simple models using the KServe v2 Inference Protocol.

## Models

1. **echo** - Returns all inputs as outputs (demonstrates basic request/response structure)
2. **add** - Adds two INT32 tensors element-wise (demonstrates tensor operations)
3. **classifier:v1** - Versioned model example (demonstrates model versioning)

## Files

- [app.py](app.py) - Server application with model handlers
- [test_client.py](test_client.py) - Test client that calls all models
- [run_example.py](run_example.py) - Complete workflow runner (starts server + runs tests)

## Quick Start

### Option 1: Run Complete Example (Recommended)

```bash
python examples/basic/run_example.py
```

This script will:
1. Start the AnyServe server
2. Wait for server to be ready
3. Run all test cases
4. Cleanup and exit

### Option 2: Manual Testing

```bash
# Terminal 1: Start server
python -m anyserve.cli examples.basic.app:app --port 8000 --workers 1

# Terminal 2: Run tests
python examples/basic/test_client.py
```

## Expected Output

```
=== AnyServe KServe Client Demo ===

Testing 'add' model...
  Request ID: req-001
  Result: [11, 22, 33]

Testing 'echo' model...
  Request ID: req-002
  Output 'output_text': [b'hello world']

Testing 'classifier' v1...
  Request ID: req-003
  Predicted class: [42]

=== All tests completed ===
```

## Next Steps

- Modify [app.py](app.py) to add your own models
- See [../../docs/architecture.md](../../docs/architecture.md) for system design
- See [../../docs/runtime.md](../../docs/runtime.md) for implementation details

# Basic Example

This example demonstrates the fundamental usage of AnyServe with three simple capabilities.

## Capabilities

1. **echo** - Returns all inputs as outputs
2. **add** - Adds two INT32 tensors element-wise
3. **classifier:v1** - Versioned capability example

## Files

- [app.py](app.py) - Server application with capability handlers
- [test_client.py](test_client.py) - Test client
- [run_example.py](run_example.py) - Complete workflow runner

## Quick Start

### Option 1: Run Complete Example (Recommended)

```bash
python examples/basic/run_example.py
```

### Option 2: Manual Testing

```bash
# Terminal 1: Start server
anyserve examples.basic.app:app --port 8000 --workers 1

# Terminal 2: Run tests
python examples/basic/test_client.py
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

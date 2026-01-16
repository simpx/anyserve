# Multi-Server Example

This example demonstrates **Client Discovery Mode** with multiple Workers registered to an API Server.

## Architecture

```
                    ┌──────────────────┐
                    │   API Server     │
                    │   :8080          │
                    │                  │
                    │  /register (SSE) │  ← Workers register here
                    │  /route          │  ← Client discovers endpoints
                    └────────┬─────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
               ┌────▼────┐       ┌────▼────┐
               │Worker 1 │       │Worker 2 │
               │ :50051  │       │ :50052  │
               │         │       │         │
               │multiply │       │ divide  │
               └─────────┘       │ power   │
                                 └─────────┘
```

## Capabilities

| Worker | Port | Capabilities |
|--------|------|--------------|
| Worker 1 | 50051 | `multiply` - Multiply two INT32 tensors |
| Worker 2 | 50052 | `divide` - Divide two FP32 tensors |
|          |       | `power` - Raise FP32 base to INT32 exponent |

## Quick Start

```bash
# Terminal 1: Start all services
./examples/multi_server/run_server.sh

# Terminal 2: Run test client
./examples/multi_server/run_client.sh
```

### Manual Testing

```bash
# Check registry
curl http://localhost:8080/registry | jq

# Route query
curl "http://localhost:8080/route?type=multiply"
# → {"endpoint":"localhost:50051","replica_id":"worker1"}

curl "http://localhost:8080/route?type=divide"
# → {"endpoint":"localhost:50052","replica_id":"worker2"}
```

## Client Discovery Mode

The Client class supports two connection modes:

### Direct Mode

Connect directly to a known Worker endpoint:

```python
from anyserve.worker.client import Client

client = Client(endpoint="localhost:50051")
result = client.infer("multiply", {"a": [1, 2], "b": [3, 4]})
```

### Discovery Mode

Discover Worker endpoints via API Server:

```python
from anyserve.worker.client import Client

# Create client with API Server and capability query
client = Client(
    api_server="http://localhost:8080",
    capability={"type": "multiply"}
)

# Infer (automatically discovers and connects to matching Worker)
result = client.infer(
    model_name="multiply",
    inputs={"a": [2, 3, 4], "b": [10, 20, 30]}
)

# Check discovered endpoint
print(f"Endpoint: {client.endpoint}")      # "localhost:50051"
print(f"Replica ID: {client.replica_id}")  # "worker1"
print(f"Mode: {client.mode}")              # ConnectionMode.DISCOVERY

client.close()
```

## Client API

```python
Client(
    endpoint=None,        # Direct mode: Worker endpoint (e.g., "localhost:50051")
    api_server=None,      # Discovery mode: API Server URL (e.g., "http://localhost:8080")
    capability=None,      # Discovery mode: Routing query dict (e.g., {"type": "multiply"})
    lazy_connect=True,    # Connect on first infer() call
)
```

| Property | Description |
|----------|-------------|
| `client.endpoint` | Current Worker endpoint (discovered or direct) |
| `client.replica_id` | Replica ID from discovery (None for direct mode) |
| `client.mode` | `ConnectionMode.DIRECT` or `ConnectionMode.DISCOVERY` |

## Files

| File | Description |
|------|-------------|
| `worker1.py` | Worker with `multiply` capability |
| `worker2.py` | Worker with `divide` and `power` capabilities |
| `test_client.py` | Test client demonstrating both connection modes |
| `run_server.sh` | Script to start all services |
| `run_client.sh` | Script to run the test client |

## Expected Output

```
==================================================
AnyServe Multi-Server Client Demo
==================================================

API Server: http://localhost:8080

==================================================
Testing 'multiply' capability (Worker 1)
==================================================
  Mode: ConnectionMode.DISCOVERY
  Endpoint (before infer): None
  Endpoint (after infer): localhost:50051
  Replica ID: worker1

  Inputs: a=[2, 3, 4], b=[10, 20, 30]
  Result: product=[20, 60, 120]
  Expected: [20, 60, 120]

==================================================
Testing 'divide' capability (Worker 2)
==================================================
  Mode: ConnectionMode.DISCOVERY
  Endpoint: localhost:50052
  Replica ID: worker2

  Inputs: a=[10.0, 20.0, 30.0], b=[2.0, 4.0, 5.0]
  Result: quotient=[5.0, 5.0, 6.0]
  Expected: [5.0, 5.0, 6.0]

==================================================
Testing 'power' capability (Worker 2)
==================================================
  Mode: ConnectionMode.DISCOVERY
  Endpoint: localhost:50052
  Replica ID: worker2

  Inputs: base=[2.0, 3.0, 4.0], exp=[2, 3, 2]
  Result: result=[4.0, 27.0, 16.0]
  Expected: [4.0, 27.0, 16.0]

==================================================
Testing Direct Mode (no API Server)
==================================================
  Mode: ConnectionMode.DIRECT
  Endpoint: localhost:50051
  Result: product=[35, 48]
  Expected: [35, 48]

==================================================
All tests completed successfully!
==================================================
```

# AnyServe MVP Demo

This demo showcases the core features of the AnyServe MVP:

1. **API Server** - Routes requests based on Capability headers
2. **Capability-based Routing** - Different handlers for different capabilities
3. **Object System** - File-based object passing between Replicas
4. **Delegation** - Automatic request forwarding

## Architecture

```
                        ┌─────────────────────────┐
                        │      API Server         │
                        │    (localhost:8080)     │
                        │                         │
                        │  - Capability Registry  │
                        │  - Request Routing      │
                        └───────────┬─────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
    ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
    │   Replica A   │       │   Replica B   │       │   Replica C   │
    │   (chat_app)  │       │  (embed_app)  │       │  (heavy_app)  │
    │               │       │               │       │               │
    │ Capabilities: │       │ Capabilities: │       │ Capabilities: │
    │ - type: chat  │       │ - type: embed │       │ - type: heavy │
    │   model: demo │       │               │       │   gpus: 2     │
    └───────────────┘       └───────────────┘       └───────────────┘
            │                       │                       │
            └───────────────────────┼───────────────────────┘
                                    │
                        ┌───────────────────────┐
                        │    Object Store       │
                        │ /tmp/anyserve-objects │
                        └───────────────────────┘
```

## Quick Start

### 1. Start the Demo

```bash
cd examples/mvp_demo
./run_demo.sh
```

This will:
- Start the API Server on port 8080
- Start 3 Worker replicas with different capabilities
- Display test commands

### 2. Run Tests

In a separate terminal:

```bash
python examples/mvp_demo/test_client.py
```

### 3. Manual Testing

```bash
# Check registered replicas
curl http://localhost:8080/registry | python -m json.tool

# Test chat capability
curl -X POST http://localhost:8080/infer/json \
  -H 'Content-Type: application/json' \
  -H 'X-Capability-Type: chat' \
  -d '{"inputs": [{"name": "text", "datatype": "BYTES", "shape": [1], "contents": {"bytes_contents": ["Hello World"]}}]}'

# Test embed capability
curl -X POST http://localhost:8080/infer/json \
  -H 'Content-Type: application/json' \
  -H 'X-Capability-Type: embed' \
  -d '{"inputs": [{"name": "text", "datatype": "BYTES", "shape": [1], "contents": {"bytes_contents": ["Sample text"]}}]}'

# Test heavy capability
curl -X POST http://localhost:8080/infer/json \
  -H 'Content-Type: application/json' \
  -H 'X-Capability-Type: heavy' \
  -d '{"inputs": [{"name": "data", "datatype": "BYTES", "shape": [1], "contents": {"bytes_contents": ["Heavy task"]}}]}'
```

## Files

| File | Description |
|------|-------------|
| `chat_app.py` | Chat capability handler using `@app.capability(type="chat")` |
| `embed_app.py` | Embedding capability handler |
| `heavy_app.py` | Heavy processing capability handler |
| `run_demo.sh` | Script to start all components |
| `test_client.py` | Test client to verify functionality |

## Key Features Demonstrated

### 1. Capability Decorator

```python
from anyserve import AnyServe, ModelInferRequest, ModelInferResponse, Context

app = AnyServe()

@app.capability(type="chat", model="demo")
def chat_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
    # Access ObjectStore
    obj_ref = context.objects.create({"data": "value"})
    data = context.objects.get(obj_ref)

    # Build response
    return ModelInferResponse(...)
```

### 2. Object System

```python
# Create an object
obj_ref = context.objects.create({"key": "value"})

# Read an object
data = context.objects.get(obj_ref)

# Objects are stored in /tmp/anyserve-objects/
# Can be passed between Replicas
```

### 3. Capability Routing

The API Server routes requests based on `X-Capability-*` headers:

```bash
# Routes to chat handler
curl -H 'X-Capability-Type: chat' ...

# Routes to embed handler
curl -H 'X-Capability-Type: embed' ...

# Routes to handler with specific model
curl -H 'X-Capability-Type: chat' -H 'X-Capability-Model: demo' ...
```

### 4. Registry

Replicas register with the API Server on startup:

```bash
# View all registered replicas
curl http://localhost:8080/registry

# Register a new replica
curl -X POST http://localhost:8080/register \
  -H 'Content-Type: application/json' \
  -d '{
    "replica_id": "my-replica",
    "endpoint": "localhost:50051",
    "capabilities": [{"type": "my-cap"}]
  }'
```

## Configuration

Environment variables and command line options:

| Option | Description | Default |
|--------|-------------|---------|
| `--port` | gRPC port for the replica | 8000 |
| `--api-server` | API Server URL | None |
| `--object-store` | Object store path | /tmp/anyserve-objects |
| `--replica-id` | Replica identifier | Auto-generated |

## Streaming Inference (Phase 7)

AnyServe supports streaming inference for LLM token generation.

### Streaming Handler

```python
from anyserve import AnyServe
from anyserve._proto import grpc_predict_v2_pb2

app = AnyServe()

@app.capability(type="chat", stream=True)
def stream_handler(request, context, stream):
    """
    Streaming handler receives a Stream object.
    Use stream.send() to send each token.
    """
    tokens = ["Hello", " ", "world", "!"]

    for i, token in enumerate(tokens):
        is_last = (i == len(tokens) - 1)

        response = grpc_predict_v2_pb2.ModelStreamInferResponse(
            infer_response=grpc_predict_v2_pb2.ModelInferResponse(
                model_name="chat",
                id=request.id,
            )
        )

        # Add text_output
        text_output = response.infer_response.outputs.add()
        text_output.name = "text_output"
        text_output.datatype = "BYTES"
        text_output.shape.append(1)
        text_output.contents.bytes_contents.append(token.encode())

        # Add finish_reason
        finish_output = response.infer_response.outputs.add()
        finish_output.name = "finish_reason"
        finish_output.datatype = "BYTES"
        finish_output.shape.append(1)
        finish_output.contents.bytes_contents.append(
            b"stop" if is_last else b""
        )

        stream.send(response)
```

### Testing Streaming

```bash
# Terminal 1: Start API Server
python -m anyserve.api_server --port 8080

# Terminal 2: Start streaming worker
anyserve examples.mvp_demo.stream_app:app --port 50051 --api-server http://localhost:8080

# Terminal 3: Test streaming
curl -N -X POST http://localhost:8080/infer/stream \
  -H 'Content-Type: application/json' \
  -H 'X-Capability-Type: chat' \
  -d '{"model_name": "chat", "inputs": [{"name": "text", "datatype": "BYTES", "shape": [1], "contents": {"bytes_contents": ["Hello"]}}]}'

# Or use the test client
python examples/mvp_demo/test_stream_client.py
```

### SSE Response Format

The `/infer/stream` endpoint returns Server-Sent Events:

```
data: {"model_name": "chat", "outputs": [{"name": "text_output", "contents": {"bytes_contents": ["Hello"]}}]}
data: {"model_name": "chat", "outputs": [{"name": "text_output", "contents": {"bytes_contents": [" "]}}]}
data: {"model_name": "chat", "outputs": [{"name": "text_output", "contents": {"bytes_contents": ["world"]}}]}
data: {"model_name": "chat", "outputs": [{"name": "text_output", "contents": {"bytes_contents": ["!"]}}, {"name": "finish_reason", "contents": {"bytes_contents": ["stop"]}}]}
```

## Next Steps

This MVP demonstrates the core architecture. Future enhancements include:

- RDMA-based Object System for high-performance data transfer
- Kubernetes integration for automatic scaling
- Production-grade API Server with authentication
- Distributed Object tracking and caching

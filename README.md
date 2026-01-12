# AnyServe

High-performance model serving framework with C++ Dispatcher and Python Worker architecture, supporting the KServe v2 inference protocol.

## Features

- **🚀 High Performance**: C++ gRPC ingress for request routing and traffic handling
- **🐍 Python Simplicity**: Write model handlers in pure Python with decorators
- **🔌 KServe Compatible**: Full support for KServe v2 inference protocol
- **📊 Multi-Model**: Serve multiple models with version support in a single deployment
- **🔄 Dynamic Registration**: Workers register models at runtime via gRPC
- **⚡ Unix Socket IPC**: High-speed inter-process communication between Ingress and Workers

## Architecture

```
External Clients (gRPC)
        ↓
   C++ Dispatcher (Port 8000)
   ├─ Model Registry
   ├─ Request Router
   └─ Worker Client
        ↓ (Unix Socket)
   Python Workers
   └─ Model Handlers (@model decorator)
```

AnyServe uses a **C++ Dispatcher + Python Worker** architecture:
- **C++ Dispatcher**: Handles all external gRPC traffic, routes requests to appropriate workers
- **Python Workers**: Independent processes running your model inference code
- **Communication**: gRPC for management, Unix Domain Sockets for high-speed inference

For detailed architecture, see:
- [System Architecture](docs/architecture.md) - Overall design and concepts
- [Runtime Architecture](docs/runtime.md) - Implementation details

## Quick Start

### Prerequisites

- Python 3.11+
- C++ compiler with C++17 support
- CMake 3.20+
- Conan 2.0+ (for C++ dependencies)

### Installation

```bash
# Install dependencies and build
just setup
just build

# Install Python package
pip install -e python/
```

### Example: Echo Model

Create `my_app.py`:

```python
from anyserve import AnyServe, ModelInferRequest, ModelInferResponse

app = AnyServe()

@app.model("echo")
def echo_handler(request: ModelInferRequest) -> ModelInferResponse:
    """Echo back all inputs as outputs"""
    response = ModelInferResponse(
        model_name=request.model_name,
        id=request.id
    )

    for inp in request.inputs:
        out = response.add_output(
            name=f"output_{inp.name}",
            datatype=inp.datatype,
            shape=inp.shape
        )
        out.contents = inp.contents

    return response
```

### Run the Server

```bash
# Start server with 1 worker
python -m anyserve.cli my_app:app --port 8000 --workers 1
```

### Test the Model

```bash
# Using the test client
python examples/basic/run_example.py
```

Or use the Python client:

```python
import grpc
from anyserve._proto import grpc_predict_v2_pb2
from anyserve._proto import grpc_predict_v2_pb2_grpc

channel = grpc.insecure_channel('localhost:8000')
stub = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(channel)

# Check server status
server_live = stub.ServerLive(grpc_predict_v2_pb2.ServerLiveRequest())
print(f"Server live: {server_live.live}")

# Check model status
model_ready = stub.ModelReady(
    grpc_predict_v2_pb2.ModelReadyRequest(name="echo")
)
print(f"Model ready: {model_ready.ready}")

# Make inference request
request = grpc_predict_v2_pb2.ModelInferRequest()
request.model_name = "echo"
request.id = "test-1"

input_tensor = request.inputs.add()
input_tensor.name = "input"
input_tensor.datatype = "INT32"
input_tensor.shape.extend([3])
input_tensor.contents.int_contents.extend([1, 2, 3])

response = stub.ModelInfer(request)
print(f"Response: {response}")
```

## Development

### Project Structure

```
anyserve/
├── cpp/                    # C++ Dispatcher implementation
│   ├── server/            # Core server components
│   │   ├── anyserve_ingress.{cpp,hpp}   # Main ingress server
│   │   ├── model_registry.{cpp,hpp}      # Model registry
│   │   └── worker_client.{cpp,hpp}       # Unix socket client
│   └── build/             # Build artifacts (gitignored)
├── python/anyserve/       # Python library
│   ├── cli.py            # CLI entry point
│   ├── kserve.py         # KServe v2 protocol
│   └── worker/           # Worker implementation
├── proto/                 # Protocol definitions
│   ├── grpc_predict_v2.proto      # KServe v2 protocol
│   └── worker_management.proto     # Worker registration
├── examples/             # Example applications
│   └── basic/           # Basic examples
├── docs/                # Documentation
└── justfile            # Build and development commands
```

### Build Commands

```bash
# Setup environment (install Conan dependencies)
just setup

# Build C++ components
just build

# Clean build artifacts
just clean

# Run tests (coming soon)
# just test
```

### Documentation

- [System Architecture](docs/architecture.md) - High-level system design
- [Runtime Architecture](docs/runtime.md) - Implementation details and component interactions
- [MVP Specification](docs/mvp.md) - Project scope and goals
- [Agent Guide](agents.md) - AI assistant collaboration guide

## Examples

See the [examples/](examples/) directory for complete examples:

- `basic/` - Basic model serving with echo, add, and classifier models
- `multi_stage/` - Multi-stage pipelines (placeholder for future)
- `streaming/` - Streaming responses (placeholder for future)

## Contributing

This project uses AI-assisted development. See [agents.md](agents.md) for collaboration guidelines.

## License

[Add your license here]

## Status

✅ **Core Features Complete**
- C++ Dispatcher server with gRPC and Unix Socket support
- Python Worker with KServe v2 protocol
- Dynamic model registration
- Multi-model serving with versioning

🚧 **In Progress**
- Performance optimization
- Monitoring and metrics
- Advanced load balancing

📋 **Planned**
- Streaming inference support
- Model auto-scaling
- Distributed deployment

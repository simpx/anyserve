# AI Agent Guide - AnyServe

> This guide helps AI agents understand the project architecture, context, and development standards for effective code maintenance and feature development.

## 1. Project Overview

**AnyServe** is a high-performance model serving framework with a **C++ Ingress + Python Worker** architecture, supporting the KServe v2 inference protocol.

**Core Principles:**
- **Performance First**: C++ handles all request routing and traffic management
- **Developer Friendly**: Write model handlers in pure Python with simple decorators
- **Protocol Standard**: Full KServe v2 compatibility for inference requests
- **Dynamic Scaling**: Workers register models at runtime, enabling flexible deployment

## 2. Architecture & Components

### 2.1 C++ Ingress (Request Router)
> Location: `cpp/server/`

**Responsibilities:**
- **gRPC Server**: Handles all external KServe v2 protocol requests
- **Model Registry**: Thread-safe mapping of model names to worker addresses
- **Request Routing**: Routes inference requests to appropriate workers
- **Worker Management**: Accepts model registrations from Python workers
- **Unix Socket Client**: High-speed IPC with worker processes

**Key Files:**
- `anyserve_ingress.{cpp,hpp}` - Main ingress server with gRPC services
- `model_registry.{cpp,hpp}` - Thread-safe model routing table
- `worker_client.{cpp,hpp}` - Unix socket communication with workers
- `main_v2.cpp` - Standalone executable entry point

**Technologies:**
- gRPC C++ for external API
- Unix Domain Sockets for worker IPC
- Protobuf for serialization

### 2.2 Python Worker (Model Inference)
> Location: `python/anyserve/`

**Responsibilities:**
- **Model Handlers**: User-defined inference logic with `@model()` decorator
- **Protocol Implementation**: KServe v2 request/response handling
- **Worker Registration**: Register models with ingress via gRPC
- **Unix Socket Server**: Listen for inference requests from ingress

**Key Files:**
- `__init__.py` - Public API (AnyServe class, decorators)
- `cli.py` - CLI entry point for starting servers
- `kserve.py` - KServe v2 protocol implementation
- `worker/__main__.py` - Worker process implementation

### 2.3 Protocol Definitions
> Location: `proto/`

- `grpc_predict_v2.proto` - KServe v2 inference protocol
- `worker_management.proto` - Worker registration protocol

## 3. Development Workflow

### Standard Development Flow

1. **Modify C++ Code** (when needed):
   - Changes to routing, registry, or IPC layer
   - Located in `cpp/server/`
   - Run `just build` to compile

2. **Modify Python Code**:
   - Model handlers, protocols, or worker logic
   - Located in `python/anyserve/`
   - No compilation needed, hot-reload in dev mode

3. **Test Changes**:
   - Run `just build` to compile C++
   - Start server: `python -m anyserve.cli examples/basic/app:app`
   - Test: `python examples/basic/run_example.py`

### Common Tasks

**Adding a New Model Handler:**
```python
# In your app.py
from anyserve import AnyServe, ModelInferRequest, ModelInferResponse

app = AnyServe()

@app.model("my_model", version="v1")
def my_handler(request: ModelInferRequest) -> ModelInferResponse:
    # Your inference logic here
    response = ModelInferResponse(
        model_name=request.model_name,
        id=request.id
    )
    # Add outputs
    return response
```

**Modifying C++ Routing Logic:**
1. Edit `cpp/server/anyserve_ingress.cpp`
2. Run `just build` to compile
3. Restart server to use new binary

**Adding Protocol Support:**
1. Define in `.proto` files
2. Regenerate: C++ build automatically regenerates
3. Python: Regenerate with protoc manually (see README)

## 4. Code Standards

### C++ Standards
- **C++17** standard
- **Namespace**: All code in `namespace anyserve`
- **Error Handling**: Use gRPC Status codes for errors
- **Thread Safety**: Model registry must be thread-safe (use mutexes)
- **Resource Management**: Use RAII (unique_ptr, etc.)
- **Style**: Follow Google C++ Style Guide

### Python Standards
- **Type Hints**: Use for all function signatures
- **PEP 8**: Follow Python style guide
- **Imports**: Use absolute imports from `anyserve`
- **Async**: Avoid mixing sync/async code
- **Documentation**: Docstrings for all public APIs

### Protocol Standards
- **KServe v2**: Strict adherence to protocol specification
- **Protobuf**: Use proto3 syntax
- **Backward Compatibility**: Don't break existing message formats

## 5. Current Implementation Status

### ✅ Completed Features
- C++ Ingress with gRPC server (KServe v2 protocol)
- Model registry with thread-safe lookups
- Unix Domain Socket IPC between Ingress and Workers
- Python Worker with model registration
- Multi-model serving with version support
- Dynamic model registration at runtime
- Basic error handling (NOT_FOUND, INTERNAL errors)

### 🚧 Known Limitations
- No connection pooling for Unix sockets (single-use connections)
- Limited error recovery and retry logic
- No metrics or monitoring yet
- No distributed deployment support

### 📋 Future Enhancements
- Streaming inference support
- Model auto-scaling based on load
- Advanced load balancing strategies
- Distributed multi-node deployment
- Performance metrics and monitoring
- Graceful shutdown and cleanup

## 6. Testing Guidelines

### Unit Tests (TODO)
- C++: Use Google Test framework
- Python: Use pytest
- Location: `tests/` directory

### Integration Tests
- Full end-to-end tests with real gRPC clients
- Located in `examples/basic/test_client.py`
- Run: `python examples/basic/test_client.py`

### Manual Testing
```bash
# Terminal 1: Start server
python -m anyserve.cli examples/basic/app:app --port 8000 --workers 1

# Terminal 2: Run test client
python examples/basic/run_example.py
```

## 7. Build System

### Justfile Commands
- `just setup` - Install Conan dependencies for C++
- `just build` - Compile C++ Ingress binary
- `just clean` - Remove build artifacts
- `just test` - Run tests (coming soon)

### Manual Build
```bash
# Install Conan dependencies
cd cpp && conan install . --build=missing

# Build with CMake
cd cpp/build && cmake .. && cmake --build .
```

## 8. Project Structure

```
anyserve/
├── cpp/                           # C++ Ingress implementation
│   ├── server/
│   │   ├── anyserve_ingress.{cpp,hpp}    # Main gRPC server
│   │   ├── model_registry.{cpp,hpp}       # Model routing table
│   │   ├── worker_client.{cpp,hpp}        # Unix socket client
│   │   └── main_v2.cpp                    # Standalone entry point
│   ├── CMakeLists.txt             # CMake build configuration
│   └── conanfile.txt              # C++ dependencies (Conan)
│
├── python/anyserve/               # Python library
│   ├── __init__.py               # Public API
│   ├── cli.py                    # CLI entry point
│   ├── kserve.py                 # KServe v2 implementation
│   └── worker/
│       └── __main__.py           # Worker process logic
│
├── proto/                         # Protocol definitions
│   ├── grpc_predict_v2.proto     # KServe v2 protocol
│   └── worker_management.proto    # Worker registration
│
├── examples/                      # Example applications
│   ├── basic/                    # Basic echo/add/classifier
│   ├── multi_stage/              # Pipeline examples (future)
│   └── streaming/                # Streaming examples (future)
│
├── docs/                         # Documentation
│   ├── architecture.md           # System architecture
│   ├── runtime.md               # Implementation details
│   └── mvp.md                   # Project scope
│
├── justfile                      # Build commands
├── README.md                     # Getting started guide
└── agents.md                     # This file
```

## 9. Debugging Tips

### C++ Debugging
- Build with debug symbols: `cmake -DCMAKE_BUILD_TYPE=Debug`
- Add logging: Use `std::cerr` (goes to stderr)
- Check process: `ps aux | grep anyserve_ingress`
- Check ports: `lsof -i :8000`

### Python Debugging
- Add print statements in handlers
- Check worker output in CLI logs
- Verify model registration: Check ingress startup logs
- Test protocol: Use `grpcurl` or Python gRPC client

### Common Issues
1. **"Failed to forward request to worker"**
   - Worker not started or crashed
   - Unix socket file missing/permissions
   - Check `/tmp/anyserve-worker-*.sock`

2. **"Model not found"**
   - Worker didn't register successfully
   - Check gRPC connection to management port
   - Verify model name/version match

3. **Proxy connection errors**
   - Unset HTTP_PROXY environment variables
   - Add `export NO_PROXY=localhost,127.0.0.1`

## 10. Key Design Decisions

### Why C++ Ingress?
- High-performance gRPC handling
- Efficient request routing without GIL
- Native thread support for concurrent requests
- Lower latency than pure Python

### Why Unix Sockets for IPC?
- Faster than TCP for local communication
- No network overhead
- Simple point-to-point communication
- Suitable for single-machine deployment

### Why Not Reuse Connections?
- Workers close connections after each request
- Simpler state management
- Avoids connection pool complexity
- Performance impact is minimal with Unix sockets

### Why KServe v2 Protocol?
- Industry standard for model serving
- Broad client library support
- Clear separation of concerns
- Extensible for future features

## 11. Contributing Guidelines

When making changes:
1. **Understand Impact**: Read relevant docs first
2. **Test Thoroughly**: Verify all 9 integration tests pass
3. **Document Changes**: Update relevant markdown files
4. **Follow Standards**: Adhere to code style guidelines
5. **Commit Messages**: Use conventional commits format

**Commit Format:**
```
type(scope): brief description

Detailed explanation if needed.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

## 12. Resources

- [KServe v2 Protocol](https://github.com/kserve/kserve/tree/master/docs/predict-api/v2)
- [gRPC C++ Documentation](https://grpc.io/docs/languages/cpp/)
- [Protocol Buffers Guide](https://developers.google.com/protocol-buffers)
- [Unix Domain Sockets](https://man7.org/linux/man-pages/man7/unix.7.html)

---

**Last Updated:** 2026-01-13

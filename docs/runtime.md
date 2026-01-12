# AnyServe Runtime Architecture

> This document describes the runtime architecture and design decisions of AnyServe.

## Overview

AnyServe uses a **C++ Dispatcher + Python Worker** architecture where:
- **C++ Dispatcher** is the main process handling all external gRPC traffic
- **Python Workers** are subprocesses that execute model inference logic
- Communication happens via Unix Domain Sockets for high-performance IPC

## Current Runtime Architecture

### System Components

```
┌─────────────────────────────────────┐
│     External gRPC Clients           │
│   (KServe v2 Protocol, Port 8000)   │
└───────────────┬─────────────────────┘
                │
    ┌───────────▼──────────────────────────────┐
    │      C++ Dispatcher (Main Process)          │
    │                                           │
    │  ┌────────────────────────────────────┐  │
    │  │      Model Registry                │  │
    │  │  (model name → worker address)     │  │
    │  │  - echo → /tmp/worker-1.sock       │  │
    │  │  - add → /tmp/worker-1.sock        │  │
    │  │  - classifier:v1 → /tmp/worker-2.sock│ │
    │  └────────────────────────────────────┘  │
    │                                           │
    │  ┌────────────────────────────────────┐  │
    │  │    KServe v2 gRPC Services         │  │
    │  │  - ModelInfer (request routing)    │  │
    │  │  - ServerLive / ServerReady        │  │
    │  │  - ModelReady                      │  │
    │  └────────────────────────────────────┘  │
    │                                           │
    │  ┌────────────────────────────────────┐  │
    │  │   Worker Management (Port 9000)    │  │
    │  │  - RegisterModel (from workers)    │  │
    │  │  - Heartbeat                       │  │
    │  └────────────────────────────────────┘  │
    └───────────┬─────────────┬─────────────────┘
                │             │
    ┌───────────▼──────┐  ┌───▼──────────────┐
    │  Python Worker 1 │  │  Python Worker 2 │
    │  @model("echo")  │  │  @model("cls:v1")│
    │  @model("add")   │  │  @model("cls:v2")│
    └──────────────────┘  └──────────────────┘
    Unix Socket           Unix Socket
    /tmp/worker-1.sock    /tmp/worker-2.sock
```

### Request Flow

#### 1. Model Inference Request (Model Exists)
```
Client → C++ Dispatcher (port 8000)
         ↓ Lookup model in registry
         ↓ Found: echo → /tmp/worker-1.sock
         ↓ Forward request via Unix Socket
         ↓
      Python Worker
         ↓ Deserialize protobuf
         ↓ Execute handler: echo_model(request)
         ↓ Serialize response
         ↓
      C++ Dispatcher
         ↓ Forward response to client
         ↓
Client ← Response
```

#### 2. Model Not Found (Fast Rejection)
```
Client → C++ Dispatcher
         ↓ Lookup model in registry
         ↓ Not Found
         ↓ Return gRPC NOT_FOUND immediately
         ↓ (No Python involvement)
Client ← Error (NOT_FOUND)
```

#### 3. Server Health Check
```
Client → C++ Dispatcher: ServerLive
         ↓ Check Dispatcher health
         ↓ Return {live: true}
         ↓ (No Python involvement)
Client ← Response
```

### Key Components

#### C++ Dispatcher

**Responsibilities:**
- Accept all external gRPC requests (KServe v2 protocol)
- Maintain thread-safe model registry
- Route inference requests to appropriate workers
- Handle worker registration and health checks
- Fast-fail on model not found

**Core Classes:**
- `AnyServeDispatcher` - Main gRPC server implementing KServe v2 services
- `ModelRegistry` - Thread-safe mapping: model_key → worker_address
- `WorkerClient` - Unix socket client for worker communication

**File Locations:**
- `cpp/server/anyserve_dispatcher.{cpp,hpp}` - Main ingress implementation
- `cpp/server/model_registry.{cpp,hpp}` - Model routing table
- `cpp/server/worker_client.{cpp,hpp}` - Worker IPC client
- `cpp/server/main_v2.cpp` - Standalone executable entry point

#### Python Worker

**Responsibilities:**
- Execute model inference logic
- Register models with ingress on startup
- Listen for inference requests via Unix socket
- Handle KServe v2 request/response serialization

**Core Classes:**
- `AnyServe` - Application class with @model decorator
- `Worker` - Worker process managing socket server and model handlers

**File Locations:**
- `python/anyserve/__init__.py` - Public API
- `python/anyserve/worker/__main__.py` - Worker process implementation
- `python/anyserve/kserve.py` - KServe v2 protocol implementation

## Why C++ Dispatcher Instead of Python + C++ Extension?

### Design Decision: C++ as Main Process

The architecture intentionally uses **C++ as the main process** rather than Python with C++ extensions. This is a critical design decision for several reasons:

#### 1. Advanced Traffic Management (Current & Future)

The ingress needs to handle complex request routing logic:
- **Request queuing**: Buffer requests during worker overload
- **Retry logic**: Automatically retry failed requests
- **Fallback routing**: Route to backup workers or models
- **Load balancing**: Distribute requests across multiple workers
- **Circuit breaking**: Detect and isolate failing workers

These operations require low-latency, high-throughput handling that's best implemented in C++. Doing this in Python would introduce significant overhead and complexity.

#### 2. Dynamic Worker Management

The system needs to support:
- **Worker registration**: Workers can join/leave at runtime
- **Worker discovery**: Automatically detect available workers
- **Health monitoring**: Track worker health and remove dead workers
- **Resource scaling**: Add/remove workers based on load

C++ provides better control over process lifecycle, socket management, and concurrent operations needed for these features.

#### 3. Zero-Python Dependency for Core Operations

Many operations don't need Python at all:
- Model not found → return 404 immediately
- Server health checks → respond without Python
- Request routing → look up registry and forward

With C++ as the main process, these operations are handled natively without crossing language boundaries.

#### 4. Performance Characteristics

**C++ Dispatcher + Python Worker:**
- One language boundary crossing per inference request
- No GIL contention for routing logic
- Native thread support for concurrent request handling
- Minimal serialization overhead (direct protobuf handling)

**Python Main + C++ Extension (Alternative):**
- Multiple language boundary crossings (Python → C++ → Python)
- GIL limitations for request routing
- Complex state management across languages
- Higher serialization overhead

#### 5. Operational Robustness

- **Isolation**: Worker crashes don't affect the ingress
- **Restart**: Workers can restart without downtime
- **Upgrades**: Update worker code without restarting ingress
- **Debugging**: Simpler to debug and profile separate processes

### Architecture Comparison

| Aspect | C++ Dispatcher (Current) | Python Main + C++ Ext (Alternative) |
|--------|----------------------|-------------------------------------|
| Main Process | C++ | Python |
| Request Entry | C++ gRPC | Python gRPC → C++ |
| Model Registry | C++ (thread-safe) | Python (GIL) |
| Routing Logic | C++ | Python |
| Worker Communication | C++ → Unix Socket → Python | Python → C++ → Python |
| Performance | High (one boundary) | Medium (multiple boundaries) |
| Scalability | Excellent (no GIL) | Limited (GIL contention) |
| Advanced Features | Native support | Complex to implement |
| Worker Isolation | Strong | Weak |

## Protocol: Worker Registration

### Startup Sequence

```
1. C++ Dispatcher starts
   - Start gRPC server on port 8000
   - Start management server on port 9000
   - Initialize empty model registry

2. Python Worker starts
   - Load all @model decorated functions
   - Start Unix socket server (e.g., /tmp/worker-abc123.sock)
   - Connect to ingress management port (9000)
   - For each model:
       → Send RegisterModel(model_name, version, worker_address)
       → Dispatcher updates registry
   - Wait for inference requests

3. Client sends inference request
   - C++ Dispatcher receives ModelInferRequest
   - Lookup model in registry
   - Forward to worker via Unix socket
   - Return response to client
```

### Worker Registration Protocol

```protobuf
// proto/worker_management.proto
service WorkerManagement {
    rpc RegisterModel(RegisterModelRequest) returns (RegisterModelResponse);
    rpc Heartbeat(HeartbeatRequest) returns (HeartbeatResponse);
}

message RegisterModelRequest {
    string model_name = 1;
    string model_version = 2;
    string worker_address = 3;  // e.g., "unix:///tmp/worker-123.sock"
    string worker_id = 4;
}
```

## Communication: Unix Domain Sockets

### Why Unix Sockets?

- **High Performance**: Faster than TCP for local IPC (no network stack overhead)
- **Zero Network Latency**: Direct kernel-level communication
- **Simple**: Point-to-point connection model
- **Secure**: Filesystem permissions control access

### Socket Protocol

**Request Format (Dispatcher → Worker):**
```
[4 bytes: message length] [N bytes: protobuf ModelInferRequest]
```

**Response Format (Worker → Dispatcher):**
```
[4 bytes: message length] [N bytes: protobuf ModelInferResponse]
```

### Connection Lifecycle

Currently, the system uses **single-use connections**:
1. Dispatcher receives request
2. Dispatcher connects to worker socket
3. Send request, receive response
4. Close connection

**Future Optimization:** Connection pooling for better performance (see Roadmap).

## Future Roadmap

### 1. Zero-Copy Communication (C++ ↔ Python)

**Current State:**
- Protobuf serialization/deserialization at language boundary
- Memory copy overhead for tensor data

**Future Goal:**
- Share memory directly between C++ and Python
- Use shared memory segments for tensor data
- Pass pointers instead of copying data
- Minimal serialization (only metadata)

**Benefits:**
- Eliminate memory copy overhead
- Reduce latency for large tensors
- Lower memory footprint
- Higher throughput

**Implementation Approach:**
- Use `mmap` or shared memory for tensor buffers
- Pass file descriptors via Unix socket ancillary data
- Use Apache Arrow or similar zero-copy format
- Python side: numpy arrays backed by shared memory

### 2. Advanced Request Management

**Request Queuing:**
- Per-model request queues with configurable depth
- Priority-based queue management
- Backpressure handling

**Retry & Fallback:**
- Automatic retry on worker failure
- Fallback to alternative workers or models
- Exponential backoff strategies

**Circuit Breaking:**
- Detect failing workers and stop routing to them
- Automatic recovery detection
- Health-based routing decisions

### 3. Connection Pooling

**Current:** Single-use Unix socket connections
**Future:** Connection pool per worker
- Reuse connections for multiple requests
- Configurable pool size
- Connection health monitoring
- Automatic connection recycling

### 4. Dynamic Worker Management

**Worker Discovery:**
- Automatic detection of new workers
- Service discovery integration (Consul, etcd)
- DNS-based worker resolution

**Auto-scaling:**
- Monitor request queue depth and latency
- Automatically spawn/kill workers
- Load-based scaling policies
- Resource-aware scheduling

**Worker Health:**
- Continuous health monitoring
- Automatic removal of dead workers
- Graceful worker shutdown
- Zero-downtime worker updates

### 5. Distributed Deployment

**Multi-node Support:**
- Dispatcher can forward to remote workers (TCP/gRPC)
- Worker pool spanning multiple machines
- Location-aware routing

**High Availability:**
- Multiple ingress instances with load balancing
- Worker redundancy and failover
- Shared model registry (Redis, etcd)

### 6. Observability

**Metrics:**
- Request latency histograms (p50, p95, p99)
- Worker utilization and queue depth
- Model-level throughput and error rates
- Resource usage (CPU, memory, GPU)

**Tracing:**
- Distributed tracing support (OpenTelemetry)
- Request flow visualization
- Performance bottleneck identification

**Logging:**
- Structured logging with correlation IDs
- Centralized log aggregation
- Debug mode with detailed protocol logs

## Development Notes

### Building the Project

```bash
# Setup dependencies
just setup

# Build C++ ingress and Python package (includes protobuf generation)
just build

# Clean all artifacts
just clean
```

### Generated Artifacts

The build process generates protobuf files in two locations:
- `python/anyserve/_proto/` - Used by worker server (kserve.py, worker/__main__.py)
- `python/anyserve/worker/proto/` - Used by gRPC client (worker/client.py)

Both are generated from the same proto files but serve different purposes in the codebase.

### Key Files

**C++ Implementation:**
- `cpp/server/main_v2.cpp` - Dispatcher entry point
- `cpp/server/anyserve_dispatcher.{cpp,hpp}` - gRPC server implementation
- `cpp/server/model_registry.{cpp,hpp}` - Model routing table
- `cpp/server/worker_client.{cpp,hpp}` - Unix socket client

**Python Implementation:**
- `python/anyserve/cli.py` - CLI entry point for starting server
- `python/anyserve/worker/__main__.py` - Worker process
- `python/anyserve/kserve.py` - KServe v2 protocol implementation
- `python/anyserve/worker/client.py` - gRPC client for testing

**Protocol Definitions:**
- `proto/grpc_predict_v2.proto` - KServe v2 inference protocol
- `proto/worker_management.proto` - Worker registration protocol

## Design Philosophy

1. **Separation of Concerns**: C++ handles routing, Python handles inference
2. **Fail Fast**: Reject invalid requests at the ingress without Python
3. **Isolation**: Worker failures don't affect the ingress or other workers
4. **Performance**: Minimize cross-language overhead and memory copies
5. **Scalability**: Support multiple workers and horizontal scaling
6. **Future-Ready**: Architecture supports advanced features like zero-copy and distributed deployment

---

**Last Updated**: 2026-01-13

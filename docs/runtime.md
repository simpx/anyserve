# anyserve Runtime Implementation

> 本文档描述 anyserve 的运行时实现细节，是 [architecture.md](./architecture.md) 的补充。
>
> architecture.md 描述"是什么"和"为什么"，本文档描述"怎么实现"。

---

## 1. 进程模型

### 架构概览

```
                         ┌─────────────────────┐
                         │   External Services │
                         │  (其他 anyserve 实例) │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │ 出流量 (Delegation) │                     │ 入流量
              ↓                     │                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                            anyserve 实例                                     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      Agent (C++, main process)                         │ │
│  │                                                                        │ │
│  │  ┌──────────────────────────┐    ┌──────────────────────────────────┐ │ │
│  │  │      入流量处理           │    │         出流量处理                │ │ │
│  │  │                          │    │                                  │ │ │
│  │  │  Port 8000: KServe v2    │    │  AnyserveClient                  │ │ │
│  │  │  (接收外部 gRPC 请求)     │    │  (向其他实例发送请求)             │ │ │
│  │  │                          │    │                                  │ │ │
│  │  │  Port 9000: Management   │    │  向 Api Server 注册 Capability  │ │ │
│  │  │  (Worker 注册)           │    │                                  │ │ │
│  │  └──────────────────────────┘    └──────────────────────────────────┘ │ │
│  │                                                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                        核心组件                                   │ │ │
│  │  │                                                                  │ │ │
│  │  │  CapabilityRegistry          WorkerClient (连接池)               │ │ │
│  │  │  capability → worker         Unix Socket → Workers               │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                     │                                        │
│                          Unix Domain Socket                                  │
│                                     │                                        │
│       ┌─────────────────────────────┼─────────────────────────────┐         │
│       ↓                             ↓                             ↓         │
│  ┌─────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐   │
│  │   Worker 0      │   │     Worker 1        │   │     Worker 2        │   │
│  │   (Python)      │   │     (C++)           │   │     (Python)        │   │
│  │                 │   │                     │   │                     │   │
│  │  capabilities:  │   │  capabilities:      │   │  ┌───────────────┐  │   │
│  │  - type: echo   │   │  - type: transcode  │   │  │   💤 IDLE     │  │   │
│  │  - type: add    │   │    codec: h264      │   │  │   (休眠中)     │  │   │
│  │                 │   │                     │   │  └───────────────┘  │   │
│  │  socket:        │   │  socket:            │   │                     │   │
│  │  /tmp/w0.sock   │   │  /tmp/w1.sock       │   │  capabilities:      │   │
│  │                 │   │                     │   │  - type: chat       │   │
│  │                 │   │                     │   │    model: llama-70b │   │
│  └─────────────────┘   └─────────────────────┘   └─────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 进程职责

| 进程 | 语言 | 职责 |
|------|------|------|
| **Agent** | C++ | 入流量接收、出流量发送、Capability 路由、Worker 管理、向 API Server 注册 |
| **Worker** | Python/C++ | 执行具体任务、注册 Capability、可休眠以节省资源 |

---

## 2. Agent 实现

### 2.1 核心类

```
cpp/server/
├── anyserve_dispatcher.{cpp,hpp}   # 主入口，gRPC server
├── model_registry.{cpp,hpp}        # model → worker 映射
├── worker_client.{cpp,hpp}         # Unix Socket 客户端 + 连接池
├── process_supervisor.{cpp,hpp}    # Worker 进程管理（待完善）
└── main.cpp                        # 可执行文件入口
```

### 2.2 AnyserveDispatcher

主类，负责：
- 启动两个 gRPC server（外部端口 + 管理端口）
- 管理 ModelRegistry 和 WorkerClient

```cpp
class AnyserveDispatcher {
    int port_;                      // 8000: KServe v2
    int management_port_;           // 9000: Worker 注册

    ModelRegistry registry_;        // model → worker 映射
    WorkerClient worker_client_;    // Unix Socket 连接池

    std::unique_ptr<grpc::Server> server_;
    std::unique_ptr<grpc::Server> management_server_;
};
```

### 2.3 CapabilityRegistry

线程安全的路由表：

```cpp
class ModelRegistry {
    // 主索引：model_key (name:version) → worker_address
    std::unordered_map<std::string, std::string> model_to_worker_;

    // 反向索引：worker_id → [model_keys]
    std::unordered_map<std::string, std::vector<std::string>> worker_to_models_;

    // 接口
    void register_model(name, version, worker_address, worker_id);
    std::optional<std::string> lookup_worker(name, version);
    size_t unregister_worker(worker_id);
};
```

**注**：当前使用 `model_name:version` 作为 key，未来会改为 capability key-value 匹配。

### 2.4 WorkerClient

Unix Socket 连接池：

```cpp
class WorkerClient {
    // 连接池：socket_path → ConnectionPool
    std::unordered_map<std::string, ConnectionPool> pools_;

    // 转发请求
    bool forward_request(
        const std::string& worker_address,
        const ModelInferRequest& request,
        ModelInferResponse& response
    );
};
```

**连接池策略**：
- 每个 Worker 最多 10 个连接
- 请求完成后归还连接
- 支持并发请求

---

## 3. Worker 实现

### 3.1 核心类

```
python/anyserve/
├── __init__.py             # 公开 API
├── kserve.py               # KServe 协议 + AnyServe 类
├── cli.py                  # CLI 入口
└── worker/
    ├── __main__.py         # Worker 进程主逻辑
    ├── loader.py           # 模块加载
    └── client.py           # gRPC 客户端（测试用）
```

### 3.2 AnyServe 类

用户定义 model handler 的入口：

```python
class AnyServe:
    _local_registry: Dict[tuple, Callable]  # (name, version) → handler

    def model(self, name: str, version: str = None):
        """装饰器，注册 model handler"""
        def decorator(func):
            self._local_registry[(name, version)] = func
            return func
        return decorator
```

### 3.3 Worker 类

Worker 进程的核心逻辑：

```python
class Worker:
    def __init__(self, app, worker_id, ingress_address, worker_port):
        self.app = app
        self.socket_path = f"/tmp/anyserve-worker-{worker_id}.sock"

    def register_to_ingress(self):
        """启动时向 Agent 注册所有 model"""
        for (model_name, version), handler in self.app._local_registry.items():
            # 通过 gRPC 调用 Agent 的 RegisterModel

    def serve(self):
        """Unix Socket 服务器主循环"""
        sock = socket.socket(AF_UNIX, SOCK_STREAM)
        sock.bind(self.socket_path)
        while running:
            conn = sock.accept()
            self.handle_connection(conn)

    def handle_connection(self, conn):
        """处理单个请求"""
        # 1. 读取请求长度 (4 bytes)
        # 2. 读取 protobuf 数据
        # 3. 调用 handler
        # 4. 发送响应
```

---

## 4. 通信协议

### 4.1 外部协议：KServe v2

外部客户端通过 KServe v2 gRPC 协议访问：

```protobuf
// proto/grpc_predict_v2.proto
service GRPCInferenceService {
    rpc ServerLive(ServerLiveRequest) returns (ServerLiveResponse);
    rpc ServerReady(ServerReadyRequest) returns (ServerReadyResponse);
    rpc ModelReady(ModelReadyRequest) returns (ModelReadyResponse);
    rpc ModelInfer(ModelInferRequest) returns (ModelInferResponse);
}
```

### 4.2 内部协议：Worker Management

Worker 向 Agent 注册：

```protobuf
// proto/worker_management.proto
service WorkerManagement {
    rpc RegisterModel(RegisterModelRequest) returns (RegisterModelResponse);
    rpc UnregisterModel(UnregisterModelRequest) returns (UnregisterModelResponse);
    rpc Heartbeat(HeartbeatRequest) returns (HeartbeatResponse);
}

message RegisterModelRequest {
    string model_name = 1;
    string model_version = 2;
    string worker_address = 3;  // "unix:///tmp/worker.sock"
    string worker_id = 4;
}
```

### 4.3 IPC 协议：Unix Socket

Agent 与 Worker 之间的请求转发：

```
┌─────────────────────────────────────────────────┐
│              Unix Socket Message                 │
│                                                  │
│   [4 bytes]           [N bytes]                  │
│   message length      protobuf data              │
│   (big-endian)        (ModelInferRequest/Response)│
│                                                  │
└─────────────────────────────────────────────────┘
```

- 请求：`length + ModelInferRequest (protobuf)`
- 响应：`length + ModelInferResponse (protobuf)`

---

## 5. 请求流程

### 5.1 完整路径

```
1. Client 发送 gRPC ModelInferRequest
   │
   ↓
2. Agent (Port 8000) 接收
   │
   ├── 解析 model_name, model_version
   │
   ├── ModelRegistry.lookup_worker(name, version)
   │   │
   │   ├── 找到 → worker_address (unix:///tmp/xxx.sock)
   │   │
   │   └── 未找到 → 返回 NOT_FOUND（不涉及 Python）
   │
   ↓
3. WorkerClient.forward_request(worker_address, request)
   │
   ├── 从连接池获取连接
   ├── 序列化 request → protobuf bytes
   ├── 发送：length + data
   │
   ↓
4. Worker 接收
   │
   ├── 解析 protobuf → ModelInferRequest
   ├── dispatch_request(request)
   │   │
   │   ├── 查找 handler: _local_registry[(name, version)]
   │   └── 调用 handler(request) → response
   │
   ├── 序列化 response → protobuf bytes
   └── 发送：length + data
   │
   ↓
5. Agent 返回响应给 Client
```

### 5.2 快速失败路径

Model 不存在时，Agent 直接返回错误，不涉及 Python：

```
Client → Agent
            │
            ├── ModelRegistry.lookup_worker() → nullopt
            │
            └── 返回 gRPC NOT_FOUND
            │
Client ← Error
```

---

## 6. Worker 定义方式

### 6.1 当前：@app.capability 装饰器

```python
from anyserve import AnyServe, ModelInferRequest, ModelInferResponse

app = AnyServe()

@app.capability(type="echo")
def echo_handler(request: ModelInferRequest) -> ModelInferResponse:
    response = ModelInferResponse(
        model_name=request.model_name,
        id=request.id
    )
    # 处理逻辑...
    return response

@app.capability(type="chat", model="llama-70b")
def chat_handler(request):
    ...

@app.capability(type="embed")
def embed_handler(request):
    ...
```

### 6.2 Streaming：@app.capability(stream=True)

```python
from anyserve import AnyServe
from anyserve._proto import grpc_predict_v2_pb2

app = AnyServe()

@app.capability(type="chat", stream=True)
def chat_stream(request, context, stream):
    """Streaming handler - 通过 stream.send() 逐步返回结果"""
    tokens = ["Hello", " ", "world", "!"]

    for i, token in enumerate(tokens):
        is_last = (i == len(tokens) - 1)

        response = grpc_predict_v2_pb2.ModelStreamInferResponse(
            infer_response=grpc_predict_v2_pb2.ModelInferResponse(
                model_name="chat",
                id=request.id,
            )
        )

        # 添加输出
        text_out = response.infer_response.outputs.add()
        text_out.name = "text_output"
        text_out.datatype = "BYTES"
        text_out.shape.append(1)
        text_out.contents.bytes_contents.append(token.encode())

        stream.send(response)
```

### 6.3 未来：Worker 类（生命周期钩子）

```python
@app.worker(
    capabilities=[{"type": "chat", "model": "llama-70b"}],
    gpus=2
)
class ChatWorker(Worker):
    def on_start(self):
        self.engine = vllm.LLM(...)

    def on_cleanup(self):
        self.engine.shutdown()

    def handle(self, request):
        return self.engine.generate(...)
```

---

## 7. 启动流程

### 7.1 通过 CLI 启动

```bash
# 启动 server（Agent + Workers）
anyserve my_app:app --port 8000 --workers 1
```

CLI 做的事情：
1. 启动 C++ Agent（port 8000, management_port 9000）
2. 启动 N 个 Python Worker 进程
3. Worker 向 Agent 注册

### 7.2 启动时序

```
1. Agent 启动
   │
   ├── 启动 KServe gRPC server (port 8000)
   ├── 启动 Management gRPC server (port 9000)
   └── 等待 Worker 注册
   │
   ↓
2. Worker 启动
   │
   ├── 加载用户 app（执行 @app.capability 装饰器）
   ├── 创建 Unix Socket (/tmp/anyserve-worker-xxx.sock)
   ├── 连接 Agent (port 9000)
   │   └── RegisterModel(model_name, version, socket_path)
   │
   └── 进入主循环，等待请求
   │
   ↓
3. Agent 更新 ModelRegistry
   │
   └── model_name:version → unix:///tmp/xxx.sock
   │
   ↓
4. 系统就绪，可接收外部请求
```

---

## 8. 文件结构

```
anyserve/
├── cpp/                          # C++ 实现
│   ├── server/
│   │   ├── anyserve_dispatcher.{cpp,hpp}   # 主入口
│   │   ├── model_registry.{cpp,hpp}        # 路由表
│   │   ├── worker_client.{cpp,hpp}         # Unix Socket 客户端
│   │   ├── process_supervisor.{cpp,hpp}    # 进程管理
│   │   └── main.cpp                        # 可执行文件入口
│   ├── core/
│   │   └── shm_manager.{cpp,hpp}           # 共享内存（预留）
│   └── build/                              # 构建产物
│
├── python/anyserve/              # Python 实现
│   ├── __init__.py               # 公开 API
│   ├── kserve.py                 # KServe 协议 + AnyServe 类
│   ├── cli.py                    # CLI 入口
│   ├── worker/
│   │   ├── __main__.py           # Worker 进程
│   │   ├── loader.py             # 模块加载
│   │   └── client.py             # gRPC 客户端
│   └── _proto/                   # 生成的 protobuf 代码
│
├── proto/                        # 协议定义
│   ├── grpc_predict_v2.proto     # KServe v2
│   ├── worker_management.proto   # Worker 注册
│   └── anyserve.proto            # 内部协议（预留）
│
├── examples/                     # 示例
│   ├── basic/
│   ├── multi_stage/
│   └── streaming/
│
└── docs/                         # 文档
    ├── architecture.md           # 架构设计
    ├── runtime.md                # 运行时实现（本文档）
    └── mvp.md                    # MVP 规划
```

---

## 9. 构建与运行

### 9.1 构建

```bash
# 安装依赖
just setup

# 构建 C++ 和 Python
just build

# 清理
just clean
```

### 9.2 运行示例

```bash
# 启动 server
anyserve examples.basic.app:app --port 8000 --workers 1

# 测试
python examples/basic/run_example.py
```

---

## 10. 未来规划

### 10.1 Capability 路由

将 ModelRegistry 改为 CapabilityRegistry：
- 支持任意 key-value 匹配
- 支持模糊匹配 / 优先级

### 10.2 Worker Manager

实现动态启停：
- 监控队列深度
- 根据 SLO 决定启停
- 资源感知

### 10.3 Object System

实现跨实例数据传输：
- 与 Agent 深度集成
- RDMA 直连
- Lazy read / Copy 语义

### 10.4 Request Queues

实现 SLO 调度：
- 按 Capability 分队列
- 优先级调度
- 背压机制

---

## 附录：关键代码位置

| 功能 | 文件 | 行号 |
|------|------|------|
| Agent 主类 | `cpp/server/anyserve_dispatcher.hpp` | 28 |
| Model 注册 | `cpp/server/model_registry.cpp` | - |
| Worker 转发 | `cpp/server/worker_client.cpp` | - |
| Python Worker | `python/anyserve/worker/__main__.py` | 55 |
| AnyServe 类 | `python/anyserve/kserve.py` | 195 |
| capability 装饰器 | `python/anyserve/kserve.py` | 405 |

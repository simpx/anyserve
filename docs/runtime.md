# AnyServe Runtime Architecture

> **Runtime Implementation Guide** - This document describes the runtime architecture
> and internal implementation details. For the overall system design, see [architecture.md](architecture.md).

## 🎯 Design Principles

1. **C++ Ingress**: Standalone main process handling all external requests
2. **Python Worker**: Independent subprocess for model inference logic
3. **Dynamic Registration**: Workers register models with Ingress on startup
4. **Zero Python Dependency**: Ingress can handle all non-inference requests independently

## 📐 架构图

```
                    ┌─────────────────────────────────────┐
                    │     External gRPC Clients           │
                    │   (KServe v2 ModelInferRequest)     │
                    └───────────────┬─────────────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │   C++ Ingress Process │
                        │   Port: 8000 (gRPC)   │
                        │                       │
                        │  ┌─────────────────┐ │
                        │  │ Model Registry  │ │
                        │  │ ┌─────────────┐ │ │
                        │  │ │ add → w1    │ │ │
                        │  │ │ echo → w1   │ │ │
                        │  │ │ cls:v1 → w2 │ │ │
                        │  │ └─────────────┘ │ │
                        │  └─────────────────┘ │
                        │                       │
                        │  ┌─────────────────┐ │
                        │  │ gRPC Router     │ │
                        │  │ - ModelInfer    │ │
                        │  │ - ServerLive    │ │
                        │  │ - ModelReady    │ │
                        │  └─────────────────┘ │
                        │                       │
                        │  ┌─────────────────┐ │
                        │  │ Management API  │ │
                        │  │ - RegisterModel │ │
                        │  │ - Heartbeat     │ │
                        │  └─────────────────┘ │
                        └───┬───────────┬───────┘
                            │           │
                  ┌─────────▼──┐   ┌───▼──────────┐
                  │  Worker 1  │   │  Worker 2    │
                  │  (Python)  │   │  (Python)    │
                  │            │   │              │
                  │  @model()  │   │  @model()    │
                  │  - add     │   │  - cls:v1    │
                  │  - echo    │   │  - cls:v2    │
                  └────────────┘   └──────────────┘
                  Unix Socket      Unix Socket
                  /tmp/w1.sock     /tmp/w2.sock
```

## 🔄 启动流程

### 1. 启动 C++ Ingress

```bash
$ ./anyserve_node --port 8000 --management-port 9000
```

**C++ 做什么**：
- 启动 gRPC 服务器（端口 8000）用于接收 KServe 请求
- 启动 gRPC 管理服务器（端口 9000）用于 Worker 注册
- 初始化空的 Model Registry
- 进入事件循环，等待请求

### 2. 启动 Python Worker

```bash
$ PYTHONPATH=python python3 examples/kserve_server.py
```

**Python 做什么**：
1. 加载所有 `@app.model()` 装饰的函数
2. 启动本地 Unix Domain Socket 服务器（例如 `/tmp/worker-12345.sock`）
3. 连接到 Ingress 的管理端口（9000）
4. 通过 `RegisterModel` RPC 注册每个模型
5. 等待 Ingress 转发请求

## 🚀 请求流程

### 场景 1: 模型存在

```
Client: ModelInferRequest(model_name="add")
  ↓
C++ Ingress (port 8000)
  ↓ 查找 Model Registry
  ↓ "add" → "unix:///tmp/worker-12345.sock" ✓
  ↓ 通过 Unix Socket 转发请求
  ↓
Python Worker (unix socket)
  ↓ 接收 protobuf bytes
  ↓ 调用 add_model(request)
  ↓ 返回 response bytes
  ↓
C++ Ingress
  ↓ 转发响应
  ↓
Client: ModelInferResponse
```

### 场景 2: 模型不存在

```
Client: ModelInferRequest(model_name="unknown")
  ↓
C++ Ingress
  ↓ 查找 Model Registry
  ↓ "unknown" → NOT_FOUND ✗
  ↓ 直接返回 gRPC NOT_FOUND
  ↓ (无需 Python 参与)
Client: gRPC Error (NOT_FOUND)
```

### 场景 3: ServerLive / ServerReady

```
Client: ServerLiveRequest
  ↓
C++ Ingress
  ↓ 直接返回 {live: true}
  ↓ (无需 Python)
Client: ServerLiveResponse
```

## 🔧 关键组件

### C++ 侧

#### 1. ModelRegistry 类
```cpp
class ModelRegistry {
public:
    void register_model(const std::string& model_key,
                       const std::string& worker_addr);

    std::optional<std::string> lookup_worker(const std::string& model_key);

    void unregister_worker(const std::string& worker_id);

private:
    std::mutex mutex_;
    std::unordered_map<std::string, std::string> model_to_worker_;
    // model_key (name:version) → worker_address
};
```

#### 2. WorkerClient 类
```cpp
class WorkerClient {
public:
    ModelInferResponse forward_request(
        const std::string& worker_addr,
        const ModelInferRequest& request
    );

private:
    std::unordered_map<std::string, std::unique_ptr<UnixSocketClient>> clients_;
};
```

#### 3. AnyserveCore 重构
```cpp
class AnyserveCore {
public:
    // 不再需要 Python dispatcher！
    // void set_dispatcher(...);  // ← 删除

    // 新增：Model Registry
    ModelRegistry& get_registry() { return registry_; }

    // 新增：Worker Client
    WorkerClient& get_worker_client() { return worker_client_; }

private:
    ModelRegistry registry_;
    WorkerClient worker_client_;
};
```

### Python 侧

#### 1. Worker 类
```python
class Worker:
    def __init__(self, ingress_address, socket_path):
        self.ingress_address = ingress_address
        self.socket_path = socket_path
        self.registry = {}  # model_key → handler

    def register_to_ingress(self):
        """向 Ingress 注册所有模型"""
        channel = grpc.insecure_channel(self.ingress_address)
        stub = WorkerManagementStub(channel)

        for (name, version), handler in self.registry.items():
            stub.RegisterModel(RegisterModelRequest(
                model_name=name,
                model_version=version or "",
                worker_address=f"unix://{self.socket_path}",
                worker_id=self.worker_id,
            ))

    def serve(self):
        """启动 Unix Socket 服务器，等待请求"""
        server = UnixSocketServer(self.socket_path)
        server.register_handler(self.handle_request)
        server.serve_forever()

    def handle_request(self, request_bytes):
        """处理来自 Ingress 的请求"""
        # 解析 protobuf
        proto_req = ModelInferRequest()
        proto_req.ParseFromString(request_bytes)

        # 转换为 Python 对象
        py_req = proto_to_python(proto_req)

        # 调用 handler
        handler = self.registry[(py_req.model_name, py_req.model_version)]
        py_resp = handler(py_req)

        # 转换回 protobuf
        proto_resp = python_to_proto(py_resp)
        return proto_resp.SerializeToString()
```

#### 2. AnyServe 类重构
```python
class AnyServe:
    def __init__(self):
        self._local_registry = {}

    def model(self, name, version=None):
        """装饰器：注册模型 handler"""
        def decorator(func):
            self._local_registry[(name, version)] = func
            return func
        return decorator

    def run(self, ingress_address="localhost:9000"):
        """作为 Worker 运行，连接到 Ingress"""
        worker = Worker(
            ingress_address=ingress_address,
            socket_path=f"/tmp/worker-{uuid.uuid4()}.sock"
        )

        # 复制 registry
        worker.registry = self._local_registry

        # 注册到 Ingress
        worker.register_to_ingress()

        # 启动服务
        worker.serve()
```

## 📊 对比：旧架构 vs 新架构

| 特性 | 旧架构（错误） | 新架构（正确） |
|------|---------------|---------------|
| 主进程 | Python | C++ |
| C++ 角色 | Python 扩展 | 独立 Ingress |
| Python 角色 | 管理者 | Worker |
| 模型注册 | Python 全局字典 | C++ Model Registry |
| 请求路由 | Python → C++ → Python | C++ → Python |
| Model 404 | 需要 Python | C++ 直接返回 |
| 多 Worker | 不支持 | 支持 |
| 性能 | 低（多次跨语言） | 高（一次转发） |

## 🎯 优势

1. **性能**：减少跨语言调用，C++ 直接路由
2. **可靠性**：Ingress 独立于 Python，不会因 Python 崩溃而中断
3. **扩展性**：支持多个 Worker，水平扩展
4. **解耦**：Python 只关心推理，C++ 只关心路由
5. **快速失败**：Model 不存在时无需查询 Python

## 🔄 下一步实现

1. ✅ 编译新的 protobuf (worker_management.proto)
2. ✅ 实现 C++ ModelRegistry 类
3. ✅ 实现 C++ WorkerManagement RPC
4. ✅ 实现 C++ → Python Unix Socket 通信
5. ✅ 重构 Python Worker 类
6. ✅ 重构 C++ main.cpp
7. ✅ 端到端测试

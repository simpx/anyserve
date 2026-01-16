# anyserve MVP

> 本文档定义 anyserve MVP（Minimum Viable Product）的实现目标和范围。
>
> 目标：**跑通核心流程，验证架构设计**，而非追求生产级性能。

---

## 1. MVP 目标

### 核心目标

1. **跑通完整请求链路**：Client → API Server → Dispatcher → Worker → 返回
2. **验证 Capability 路由**：基于 key-value 的请求分发
3. **验证 Worker 动态管理**：启停 Worker，切换 Capability
4. **验证 Object System 概念**：跨 Replica 数据传递（简化实现）
5. **验证 Delegation**：请求转发机制
6. **支持流式推理**：Server Streaming 模式，支持 LLM token 流式输出

### 简化策略

| 组件 | 生产版本 | MVP 版本 |
|------|----------|----------|
| API Server | 独立项目，高性能 | 简单实现，演示用 |
| 资源管理 | K8s Gang Scheduling | 用户手动运行进程 |
| Object System | RDMA 直连，零拷贝 | 共享文件系统（目录） |
| IPC | 零拷贝共享内存 | Unix Socket + protobuf |
| 多机 | 自动发现，编排 | 用户手动配置 |
| **流式接口** | 高性能双向流 | Server Streaming + SSE |

---

## 2. 系统架构（MVP）

```
┌─────────────────────────────────────────────────────────────────┐
│                        MVP 演示环境                              │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              API Server (Python, 演示用)                 │   │
│   │                                                          │   │
│   │   - HTTP/gRPC 入口                                       │   │
│   │   - Capability 注册表                                    │   │
│   │   - 根据 Capability 路由到 Replica                       │   │
│   │   - 流式响应 (SSE)                                       │   │
│   │                                                          │   │
│   │   Port: 8080                                             │   │
│   └─────────────────────────────┬───────────────────────────┘   │
│                                 │                                │
│               ┌─────────────────┼─────────────────┐             │
│               ↓                 ↓                 ↓             │
│   ┌───────────────────┐ ┌───────────────────┐ ┌───────────────┐│
│   │  Replica A        │ │  Replica B        │ │  Replica C    ││
│   │  (anyserve)       │ │  (anyserve)       │ │  (anyserve)   ││
│   │                   │ │                   │ │               ││
│   │  Port: 50051      │ │  Port: 50052      │ │  Port: 50053  ││
│   │  Caps: chat       │ │  Caps: embed      │ │  Caps: heavy  ││
│   │  (stream support) │ │                   │ │               ││
│   └───────────────────┘ └───────────────────┘ └───────────────┘│
│               │                 │                 │             │
│               └─────────────────┼─────────────────┘             │
│                                 ↓                                │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Object Store (共享目录)                     │   │
│   │                                                          │   │
│   │   /tmp/anyserve-objects/                                 │   │
│   │   ├── obj-abc123.bin                                     │   │
│   │   ├── obj-def456.bin                                     │   │
│   │   └── ...                                                │   │
│   │                                                          │   │
│   │   单机：本地目录                                          │   │
│   │   多机：NAS / NFS / 其他共享存储                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 组件设计

### 3.1 API Server（演示用）

**实现语言**：Python（FastAPI），简单快速

**职责**：
- 接收外部请求（HTTP + gRPC）
- 维护 Capability → Replica 注册表
- 根据请求的 Capability 路由到对应 Replica
- 转发请求，返回响应
- **流式响应转发（gRPC stream → SSE）**

**接口设计**：

```python
# 注册接口（Replica 启动时调用）
POST /register
{
    "replica_id": "replica-a",
    "endpoint": "localhost:50051",
    "capabilities": [
        {"type": "chat", "model": "llama-70b"},
        {"type": "chat", "model": "llama-7b"}
    ]
}

# 推理接口（Client 调用）- 非流式
POST /infer
Headers:
    X-Capability-Type: chat
    X-Capability-Model: llama-70b
Body:
    <KServe v2 ModelInferRequest>

# 推理接口（Client 调用）- 流式
POST /infer/stream
Headers:
    X-Capability-Type: chat
    X-Capability-Model: llama-70b
Body:
    <KServe v2 ModelInferRequest>
Response:
    Content-Type: text/event-stream
    data: <ModelStreamInferResponse serialized>
    data: <ModelStreamInferResponse serialized>
    ...

# 查询注册表
GET /registry
```

**路由逻辑**：
1. 从 Header 提取 Capability key-value
2. 在注册表中查找匹配的 Replica
3. 转发请求到 Replica
4. 如果没有匹配，返回 404 或随机选一个（触发 Delegation）

### 3.2 anyserve Replica

**已有实现**：C++ Dispatcher + Python Worker

**MVP 新增**：
- 启动时向 API Server 注册
- Capability 路由（替代 model name 路由）
- Delegation 支持
- Object System 集成（文件系统版）
- **流式推理支持（ModelStreamInfer RPC）**

**启动方式**（用户手动）：

```bash
# 启动 Replica A
anyserve start \
    --port 50051 \
    --api-server http://localhost:8080 \
    --app my_app:app \
    --object-store /tmp/anyserve-objects

# 启动 Replica B（另一个终端）
anyserve start \
    --port 50052 \
    --api-server http://localhost:8080 \
    --app my_app:app \
    --object-store /tmp/anyserve-objects
```

### 3.3 Object System（简化版）

**实现方式**：共享文件系统

**机制**：
- Object = 文件（`/tmp/anyserve-objects/obj-{uuid}.bin`）
- ObjRef = 文件路径字符串
- 创建：写文件，返回路径
- 读取：读文件
- 跨 Replica：假设同一目录可访问（单机）或挂载共享存储（多机）

**API**：

```python
# 创建 Object
obj_ref = anyserve.objects.create(data)
# 返回: "/tmp/anyserve-objects/obj-abc123.bin"

# 读取 Object
data = anyserve.objects.get(obj_ref)

# 跨 Replica 调用时传递
result = anyserve.call(
    capability={"type": "embed"},
    inputs={"image": obj_ref}  # 传递路径
)
```

**简化点**：
- 无 RDMA，直接文件 I/O
- 无 Lazy Read，直接读取
- 无 Cache/Tracker，简单 TTL 清理

### 3.4 Worker 定义（非流式）

**MVP 目标**：支持 `@app.capability` 装饰器，使用原生 KServe proto 类型

```python
from anyserve import AnyServe
from anyserve.proto import ModelInferRequest, ModelInferResponse

app = AnyServe()

@app.capability(type="chat", model="llama-70b")
def chat_handler(request: ModelInferRequest, context) -> ModelInferResponse:
    # context.objects 可以访问 Object System
    # request 是原生 KServe proto 类型

    # 构造原生 KServe 响应
    return ModelInferResponse(
        model_name="llama-70b",
        id=request.id,
        outputs=[
            ModelInferResponse.InferOutputTensor(
                name="output",
                datatype="BYTES",
                shape=[1],
                contents=ModelInferResponse.InferTensorContents(
                    bytes_contents=[b"Hello, world!"]
                )
            )
        ]
    )
```

### 3.5 Worker 定义（流式）

**MVP 目标**：支持 `@app.capability(stream=True)` 装饰器

```python
from anyserve import AnyServe
from anyserve.proto import (
    ModelInferRequest,
    ModelInferResponse,
    ModelStreamInferResponse,
)

app = AnyServe()

@app.capability(type="chat", stream=True)
def chat_stream_handler(request: ModelInferRequest, context, stream) -> None:
    """
    流式 handler：
    - request: 原生 ModelInferRequest
    - context: Context 对象（objects, call 等）
    - stream: Stream 对象，用于发送流式响应
    - 返回值: None（通过 stream.send() 发送响应）
    """

    # 模拟 token 生成
    tokens = ["Hello", " ", "world", "!"]

    for i, token in enumerate(tokens):
        is_last = (i == len(tokens) - 1)

        # 构造并发送原生 KServe 流式响应
        response = ModelStreamInferResponse(
            error_message="",
            infer_response=ModelInferResponse(
                model_name="llama-70b",
                id=request.id,
                outputs=[
                    ModelInferResponse.InferOutputTensor(
                        name="text_output",
                        datatype="BYTES",
                        shape=[1],
                        contents=ModelInferResponse.InferTensorContents(
                            bytes_contents=[token.encode()]
                        )
                    ),
                    ModelInferResponse.InferOutputTensor(
                        name="finish_reason",
                        datatype="BYTES",
                        shape=[1],
                        contents=ModelInferResponse.InferTensorContents(
                            bytes_contents=[b"stop" if is_last else b""]
                        )
                    )
                ]
            )
        )
        stream.send(response)
```

---

## 4. 核心流程

### 4.1 启动流程

```
1. 启动 API Server
   $ python -m anyserve.api_server --port 8080

2. 启动 Replica A
   $ anyserve start --port 50051 --api-server http://localhost:8080 --app app_a:app
   │
   ├── Dispatcher 启动
   ├── Worker 启动，加载 @capability handlers
   └── 向 API Server 注册: POST /register
       {replica_id, endpoint, capabilities}

3. 启动 Replica B（类似）
   $ anyserve start --port 50052 --api-server http://localhost:8080 --app app_b:app

4. 系统就绪
```

### 4.2 请求流程（非流式）

```
Client
  │
  │ POST /infer
  │ Headers: X-Capability-Type=chat, X-Capability-Model=llama-70b
  │ Body: {inputs: ...}
  │
  ↓
API Server
  │
  ├── 提取 Capability: {type: chat, model: llama-70b}
  ├── 查找注册表 → Replica A (localhost:50051)
  ├── 转发请求到 Replica A
  │
  ↓
Replica A (Dispatcher)
  │
  ├── 查找匹配的 Worker
  ├── 分发请求
  │
  ↓
Worker
  │
  ├── 执行 chat_handler(request, context)
  ├── 可能访问 Object System
  ├── 返回 ModelInferResponse
  │
  ↓
← 响应返回 Client
```

### 4.3 请求流程（流式）

```
Client
  │
  │ POST /infer/stream
  │ Headers: X-Capability-Type=chat
  │ Body: ModelInferRequest
  │
  ↓
API Server
  │
  ├── 提取 Capability: {type: chat}
  ├── 查找注册表 → Replica A (localhost:50051)
  ├── 调用 Replica A 的 ModelStreamInfer RPC (gRPC server streaming)
  │
  ↓
Replica A (Worker)
  │
  ├── 执行 chat_stream_handler(request, context, stream)
  │
  │   stream.send(ModelStreamInferResponse{token: "Hello"})
  │   ─────────────────────────────────────────────────────→ SSE: data: {...}
  │
  │   stream.send(ModelStreamInferResponse{token: " "})
  │   ─────────────────────────────────────────────────────→ SSE: data: {...}
  │
  │   stream.send(ModelStreamInferResponse{token: "world"})
  │   ─────────────────────────────────────────────────────→ SSE: data: {...}
  │
  │   stream.send(ModelStreamInferResponse{token: "!", finish: "stop"})
  │   ─────────────────────────────────────────────────────→ SSE: data: {...}
  │
  ↓
← 流结束
```

### 4.4 Delegation 流程

```
Client
  │
  │ POST /infer
  │ Headers: X-Capability-Type=heavy
  │
  ↓
API Server
  │
  ├── 查找注册表 → 没有匹配
  ├── 随机选择 Replica A
  │
  ↓
Replica A (Dispatcher)
  │
  ├── 查找 Worker → 没有 heavy capability
  ├── 发起 Delegation
  │   │
  │   └── POST /infer to API Server
  │       Headers: X-Capability-Type=heavy, X-Delegated-From=replica-a
  │
  ↓
API Server
  │
  ├── 重新查找（排除 replica-a）→ Replica C
  │
  ↓
Replica C
  │
  ├── 执行请求
  │
  ↓
← 响应返回（经 Replica A）→ Client
```

### 4.5 Object 传递流程

```
Replica A                              Replica B
    │                                      │
    │ 1. 创建 Object                        │
    │    obj_ref = objects.create(data)    │
    │    → 写文件 /tmp/.../obj-xxx.bin     │
    │                                      │
    │ 2. 调用 Replica B                     │
    │    anyserve.call(                    │
    │      cap={type: embed},              │
    │      inputs={data: obj_ref}          │
    │    )                                 │
    │ ─────────────────────────────────────→│
    │    (经过 API Server 路由)             │
    │                                      │
    │                                      │ 3. 读取 Object
    │                                      │    data = objects.get(obj_ref)
    │                                      │    → 读文件 /tmp/.../obj-xxx.bin
    │                                      │
    │                                      │ 4. 处理并返回
    │ ←─────────────────────────────────────│
    │                                      │
```

---

## 5. 当前代码状态

### 已实现

| 组件 | 状态 | 文件位置 |
|------|------|----------|
| C++ Dispatcher | ✅ 完成 | `cpp/server/anyserve_dispatcher.cpp` |
| ModelRegistry | ✅ 完成 | `cpp/server/model_registry.cpp` |
| WorkerClient (连接池) | ✅ 完成 | `cpp/server/worker_client.cpp` |
| Python Worker | ✅ 完成 | `python/anyserve/worker/__main__.py` |
| `@app.model` 装饰器 | ✅ 完成 | `python/anyserve/kserve.py` |
| CLI 启动器 | ✅ 完成 | `python/anyserve/cli.py` |
| KServe v2 协议 | ✅ 完成 | `proto/grpc_predict_v2.proto` |
| Worker 注册协议 | ✅ 完成 | `proto/worker_management.proto` |
| 基础示例 | ✅ 完成 | `examples/basic/app.py` |
| **API Server** | ✅ 完成 | `python/anyserve/api_server/` |
| **Capability Registry** | ✅ 完成 | `python/anyserve/api_server/registry.py` |
| **Capability Router** | ✅ 完成 | `python/anyserve/api_server/router.py` |
| **`@app.capability` 装饰器** | ✅ 完成 | `python/anyserve/kserve.py` |
| **Object System** | ✅ 完成 | `python/anyserve/objects/store.py` |
| **Delegation** | ✅ 完成 | `python/anyserve/api_server/router.py` |
| **MVP Demo** | ✅ 完成 | `examples/mvp_demo/` |
| **Test Suite** | ✅ 完成 | `tests/` (92 tests passing) |

### 待实现

| 组件 | 状态 | 说明 |
|------|------|------|
| Worker 动态管理 | ⚠️ 部分 | ProcessSupervisor 存在但不完整 |
| **流式接口** | ✅ 完成 | Phase 7 |

---

## 6. 实现计划

### Phase 1：API Server（演示用） ✅ 已完成

**目标**：实现一个简单的 API Server，作为请求入口和路由器

**新建文件**：
- `python/anyserve/api_server/__init__.py`
- `python/anyserve/api_server/__main__.py`
- `python/anyserve/api_server/registry.py`
- `python/anyserve/api_server/router.py`

**任务列表**：

- [x] **1.1 创建 FastAPI 应用骨架**
- [x] **1.2 实现 Capability 注册表**
- [x] **1.3 实现注册接口**
- [x] **1.4 实现路由转发**
- [x] **1.5 编写测试**

---

### Phase 2：Capability 路由 ✅ 已完成

**目标**：将 model name 路由改为 Capability key-value 路由

**任务列表**：

- [x] **2.1 添加 `@app.capability` 装饰器**
- [x] **2.2 修改 Worker 注册逻辑**
- [ ] **2.3 修改 proto 定义** *(MVP 中跳过，Python 层直接实现)*
- [ ] **2.4 修改 C++ ModelRegistry** *(MVP 中跳过，Python 层直接实现)*
- [x] **2.5 Replica 向 API Server 注册**
- [x] **2.6 更新示例**

---

### Phase 3：Object System（文件版） ✅ 已完成

**目标**：实现简化版 Object System，基于共享文件系统

**任务列表**：

- [x] **3.1 实现 ObjectStore 类**
- [x] **3.2 实现 ObjRef 类**
- [x] **3.3 集成到 Worker Context**
- [x] **3.4 实现 anyserve.call()**
- [x] **3.5 编写示例**

---

### Phase 4：Delegation ✅ 已完成

**目标**：实现请求转发机制

**任务列表**：

- [ ] **4.1 Dispatcher 检测无法处理的请求** *(MVP 中跳过，API Server 层实现)*
- [ ] **4.2 Dispatcher 发起 Delegation** *(MVP 中跳过，API Server 层实现)*
- [x] **4.3 API Server 处理 Delegation**
- [x] **4.4 防止无限循环**
- [x] **4.5 编写测试**

---

### Phase 5：Worker 动态管理 ⏳ 待实现

**目标**：实现 Worker 的动态启停

**任务列表**：

- [ ] **5.1 完善 ProcessSupervisor**
- [ ] **5.2 实现 Worker Manager**
- [ ] **5.3 Worker 资源声明**
- [ ] **5.4 实现 Worker 类（可选）**
- [ ] **5.5 动态启停演示**

---

### Phase 6：集成演示 ✅ 已完成

**目标**：端到端演示所有功能

**任务列表**：

- [x] **6.1 多 Replica 演示**
- [x] **6.2 Capability 路由演示**
- [x] **6.3 Delegation 演示**
- [x] **6.4 Object 传递演示**
- [x] **6.5 文档**

---

### Phase 7：流式接口 ✅ 已完成

**目标**：支持 Server Streaming 模式的流式推理

#### 7.1 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| RPC 类型 | Server Streaming | 单请求多响应，满足 LLM 场景，实现简单 |
| Handler API | `stream=True` 参数 | 同一装饰器，显式区分流式/非流式 |
| Proto 类型 | 原生 KServe proto | MVP 保持简单，不做封装 |
| HTTP 协议 | SSE (Server-Sent Events) | 简单，兼容性好，OpenAI API 同款 |

#### 7.2 Wire Format

流式响应基于 KServe 扩展的 `ModelStreamInferResponse`：

```protobuf
// 新增 RPC
rpc ModelStreamInfer(ModelInferRequest) returns (stream ModelStreamInferResponse) {}

// 新增消息
message ModelStreamInferResponse {
  string error_message = 1;           // 空字符串表示成功
  ModelInferResponse infer_response = 2;  // 包含本次的 outputs
}
```

每次流式响应发送一个完整的 `ModelStreamInferResponse`，包含：
- `error_message`: 错误信息（空表示成功）
- `infer_response`: 完整的 `ModelInferResponse`，其中 `outputs` 包含本次的数据

**典型 LLM 场景的 outputs**：

| Output Name | Type | 说明 |
|-------------|------|------|
| `text_output` | BYTES | 本次生成的 token |
| `finish_reason` | BYTES | 空=继续，"stop"=正常结束，"length"=达到长度限制 |

**流式响应序列示例**：

```
Response 1: text_output="Hello"    finish_reason=""
Response 2: text_output=" world"   finish_reason=""
Response 3: text_output="!"        finish_reason="stop"  ← 最后一条
```

#### 7.3 任务列表

##### 7.3.1 Proto 层

**修改文件**: `proto/grpc_predict_v2.proto`

- [x] **7.3.1.1 添加 ModelStreamInfer RPC**
  ```protobuf
  service GRPCInferenceService {
    // 现有
    rpc ModelInfer(ModelInferRequest) returns (ModelInferResponse) {}

    // 新增
    rpc ModelStreamInfer(ModelInferRequest) returns (stream ModelStreamInferResponse) {}
  }
  ```

- [x] **7.3.1.2 添加 ModelStreamInferResponse 消息**
  ```protobuf
  message ModelStreamInferResponse {
    string error_message = 1;
    ModelInferResponse infer_response = 2;
  }
  ```

- [x] **7.3.1.3 重新生成 Python proto 代码**
  ```bash
  python -m grpc_tools.protoc -I. --python_out=python/anyserve/_proto \
      --grpc_python_out=python/anyserve/_proto proto/grpc_predict_v2.proto
  ```

##### 7.3.2 kserve.py 改造

**修改文件**: `python/anyserve/kserve.py`

- [x] **7.3.2.1 移除 Python wrapper 类，改用原生 proto**
  - 移除 `ModelInferRequest`, `ModelInferResponse` 等 Python dataclass
  - 从 `anyserve._proto.grpc_predict_v2_pb2` 导入原生类型
  - 保持向后兼容：在 `__init__.py` 中 re-export

- [x] **7.3.2.2 添加 Stream 类**
  ```python
  class Stream:
      """gRPC stream 的薄封装"""

      def __init__(self, grpc_context):
          self._context = grpc_context

      def send(self, response: ModelStreamInferResponse) -> None:
          """发送原生 proto 消息到 gRPC stream"""
          self._context.write(response)

      def error(self, message: str) -> None:
          """发送错误响应"""
          self.send(ModelStreamInferResponse(error_message=message))
  ```

- [x] **7.3.2.3 修改 @app.capability 装饰器**
  ```python
  def capability(self, stream: bool = False, **capability_attrs):
      """
      stream=False: 非流式
          handler 签名: (request: ModelInferRequest, context) -> ModelInferResponse

      stream=True: 流式
          handler 签名: (request: ModelInferRequest, context, stream: Stream) -> None
      """
      def decorator(func):
          # 检查参数个数区分流式/非流式
          sig = inspect.signature(func)
          params = list(sig.parameters.keys())

          # 存储 handler 信息
          self._capability_handlers.append({
              'capability': Capability(**capability_attrs),
              'handler': func,
              'stream': stream,
              'uses_context': len(params) >= 2,
          })
          return func
      return decorator
  ```

- [x] **7.3.2.4 添加 find_stream_handler 方法**
  ```python
  def find_stream_handler(self, capability_query: Dict) -> Optional[tuple]:
      """查找流式 handler"""
      for h in self._capability_handlers:
          if h['stream'] and h['capability'].matches(capability_query):
              return (h['handler'], h['uses_context'])
      return None
  ```

##### 7.3.3 Worker 层

**修改文件**: `python/anyserve/worker/__main__.py`

- [x] **7.3.3.1 实现 ModelStreamInfer RPC handler**
  ```python
  def ModelStreamInfer(self, request, context):
      """gRPC server streaming handler"""
      # 提取 capability
      cap_query = self._extract_capability(request)

      # 查找流式 handler
      result = self.app.find_stream_handler(cap_query)
      if not result:
          # 发送错误
          yield ModelStreamInferResponse(error_message="No stream handler found")
          return

      handler, uses_context = result

      # 创建 Stream 对象
      stream = Stream(context)

      # 调用 handler
      ctx = self._create_context()
      handler(request, ctx, stream)

      # handler 通过 stream.send() 发送响应
  ```

- [x] **7.3.3.2 实现 Stream.send() 的实际逻辑**
  - Stream 内部维护一个 queue
  - handler 调用 send() 时放入 queue
  - gRPC handler 从 queue 中 yield

##### 7.3.4 API Server 层

**修改文件**: `python/anyserve/api_server/router.py`

- [x] **7.3.4.1 添加 /infer/stream 端点**
  ```python
  from fastapi.responses import StreamingResponse

  @app.post("/infer/stream")
  async def infer_stream(
      request: Request,
      x_capability_type: Optional[str] = Header(None),
      ...
  ):
      # 提取 capability
      capability = extract_capability(headers)

      # 查找 replica
      replica = registry.lookup(capability)

      # 调用 gRPC streaming
      async def event_generator():
          async with grpc.aio.insecure_channel(replica.endpoint) as channel:
              stub = GRPCInferenceServiceStub(channel)
              async for response in stub.ModelStreamInfer(grpc_request):
                  # 序列化为 JSON 或 hex
                  data = serialize_response(response)
                  yield f"data: {data}\n\n"

      return StreamingResponse(
          event_generator(),
          media_type="text/event-stream"
      )
  ```

- [x] **7.3.4.2 实现 gRPC stream → SSE 转换**
  - 每个 `ModelStreamInferResponse` 转为一个 SSE event
  - 序列化格式：JSON 或 protobuf hex

##### 7.3.5 示例和测试

**新建文件**:
- `examples/mvp_demo/stream_app.py`
- `tests/unit/kserve/test_stream.py`
- `tests/integration/test_streaming.py`

- [x] **7.3.5.1 创建流式示例 stream_app.py**
  ```python
  from anyserve import AnyServe
  from anyserve.proto import (
      ModelInferRequest,
      ModelInferResponse,
      ModelStreamInferResponse,
  )

  app = AnyServe()

  @app.capability(type="chat", stream=True)
  def chat_stream(request: ModelInferRequest, context, stream):
      """流式 chat handler"""
      # 模拟 token 生成
      tokens = ["Hello", " ", "world", "!"]

      for i, token in enumerate(tokens):
          is_last = (i == len(tokens) - 1)

          response = ModelStreamInferResponse(
              error_message="",
              infer_response=ModelInferResponse(
                  model_name="demo",
                  id=request.id,
                  outputs=[
                      ModelInferResponse.InferOutputTensor(
                          name="text_output",
                          datatype="BYTES",
                          shape=[1],
                          contents=ModelInferResponse.InferTensorContents(
                              bytes_contents=[token.encode()]
                          )
                      ),
                      ModelInferResponse.InferOutputTensor(
                          name="finish_reason",
                          datatype="BYTES",
                          shape=[1],
                          contents=ModelInferResponse.InferTensorContents(
                              bytes_contents=[b"stop" if is_last else b""]
                          )
                      )
                  ]
              )
          )
          stream.send(response)
  ```

- [x] **7.3.5.2 更新 run_demo.sh 支持流式演示**

- [x] **7.3.5.3 添加流式单元测试**
  - Stream 类测试
  - @app.capability(stream=True) 装饰器测试
  - handler 查找测试

- [x] **7.3.5.4 添加流式集成测试**
  - 端到端流式请求测试
  - SSE 响应解析测试

##### 7.3.6 文档更新

- [x] **7.3.6.1 更新 examples/mvp_demo/README.md**
- [x] **7.3.6.2 更新 docs/test-plan.md**

#### 7.4 文件改动清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `proto/grpc_predict_v2.proto` | 修改 | 添加 streaming RPC 和消息 |
| `python/anyserve/_proto/*.py` | 重新生成 | proto 生成代码 |
| `python/anyserve/kserve.py` | 大改 | 使用原生 proto，添加 Stream 类 |
| `python/anyserve/__init__.py` | 修改 | re-export 原生 proto 类型 |
| `python/anyserve/worker/__main__.py` | 修改 | 支持流式 handler |
| `python/anyserve/api_server/router.py` | 修改 | 添加 SSE 端点 |
| `examples/mvp_demo/stream_app.py` | 新建 | 流式示例 |
| `tests/unit/kserve/test_stream.py` | 新建 | 流式单元测试 |
| `tests/integration/test_streaming.py` | 新建 | 流式集成测试 |

---

## 7. 演示场景

### 场景 1：基本路由

```bash
# 终端 1：启动 API Server
python -m anyserve.api_server --port 8080

# 终端 2：启动 Replica A（提供 chat capability）
anyserve start --port 50051 --api-server http://localhost:8080 \
    --app examples.chat_app:app

# 终端 3：启动 Replica B（提供 embed capability）
anyserve start --port 50052 --api-server http://localhost:8080 \
    --app examples.embed_app:app

# 终端 4：测试
curl -X POST http://localhost:8080/infer \
    -H "X-Capability-Type: chat" \
    -d '{"inputs": ...}'
# → 路由到 Replica A

curl -X POST http://localhost:8080/infer \
    -H "X-Capability-Type: embed" \
    -d '{"inputs": ...}'
# → 路由到 Replica B
```

### 场景 2：Delegation

```bash
# 发送请求到不存在的 Capability
curl -X POST http://localhost:8080/infer \
    -H "X-Capability-Type: unknown" \
    -d '{"inputs": ...}'

# API Server 随机选择 Replica A
# Replica A 发现无法处理，发起 Delegation
# API Server 重新路由（可能返回错误或找到其他 Replica）
```

### 场景 3：Object 传递

```python
# chat_app.py
@app.capability(type="chat")
def chat_handler(request, context):
    # 创建中间结果
    embedding = compute_embedding(request.inputs["text"])
    obj_ref = context.objects.create(embedding)

    # 调用 embed Replica 做进一步处理
    result = context.call(
        capability={"type": "embed"},
        inputs={"embedding": obj_ref}
    )

    return result
```

### 场景 4：流式推理

```bash
# 终端 1：启动 API Server
python -m anyserve.api_server --port 8080

# 终端 2：启动 Replica（提供流式 chat capability）
anyserve start --port 50051 --api-server http://localhost:8080 \
    --app examples.stream_app:app

# 终端 3：测试流式请求
curl -N -X POST http://localhost:8080/infer/stream \
    -H "X-Capability-Type: chat" \
    -H "Content-Type: application/json" \
    -d '{"model_name": "chat", "inputs": [...]}'

# 输出（SSE 格式）：
# data: {"text_output": "Hello", "finish_reason": ""}
# data: {"text_output": " world", "finish_reason": ""}
# data: {"text_output": "!", "finish_reason": "stop"}
```

### 场景 5：Worker 动态启停

```bash
# 初始状态：Replica A 只有 chat Worker

# 发送 heavy 请求
curl -X POST ... -H "X-Capability-Type: heavy"
# → Replica A 收到，发现没有 heavy Worker

# Worker Manager 决定启动 heavy Worker
# → 动态加载 heavy_handler
# → 向 API Server 更新注册

# 重试请求
# → 成功处理
```

---

## 8. 不在 MVP 范围

以下功能 **不在 MVP 范围内**：

- K8s 集成 / Gang Scheduling
- RDMA / 零拷贝
- 真正的分布式 Object System
- 生产级 API Server
- 高可用 / 故障恢复
- 监控 / 指标
- 多机自动发现
- 双向流式 (Bidirectional Streaming)
- WebSocket 协议

这些功能将在后续版本中实现。

---

## 9. 成功标准

MVP 完成时，应能演示：

1. ✅ Client 通过 API Server 访问多个 Replica
2. ✅ 请求根据 Capability 正确路由
3. ✅ Delegation 机制工作正常
4. ✅ Object 可以在 Replica 之间传递
5. ⏳ Worker 可以动态启停 *(Phase 5 待实现)*
6. ✅ 有清晰的使用文档和演示脚本
7. ✅ 完整的测试套件 (92 tests passing)
8. ✅ 流式推理正常工作

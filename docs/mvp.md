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

### 简化策略

| 组件 | 生产版本 | MVP 版本 |
|------|----------|----------|
| API Server | 独立项目，高性能 | 简单实现，演示用 |
| 资源管理 | K8s Gang Scheduling | 用户手动运行进程 |
| Object System | RDMA 直连，零拷贝 | 共享文件系统（目录） |
| IPC | 零拷贝共享内存 | Unix Socket + protobuf |
| 多机 | 自动发现，编排 | 用户手动配置 |

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

# 推理接口（Client 调用）
POST /infer
Headers:
    X-Capability-Type: chat
    X-Capability-Model: llama-70b
Body:
    <KServe v2 ModelInferRequest>

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

### 3.4 Worker 定义

**MVP 目标**：支持 `@app.capability` 装饰器

```python
from anyserve import AnyServe

app = AnyServe()

@app.capability(type="chat", model="llama-70b")
def chat_handler(request, context):
    # context.objects 可以访问 Object System
    image_data = context.objects.get(request.inputs["image"])

    # 处理逻辑...

    # 创建输出 Object
    result_ref = context.objects.create(result_data)

    return {"output": result_ref}


@app.capability(type="embed")
def embed_handler(request, context):
    ...
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

### 4.2 请求流程

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
  ├── 返回响应
  │
  ↓
← 响应返回 Client
```

### 4.3 Delegation 流程

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

### 4.4 Object 传递流程

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

---

## 6. 实现计划

### Phase 1：API Server（演示用）

**目标**：实现一个简单的 API Server，作为请求入口和路由器

**新建文件**：
- `python/anyserve/api_server/__init__.py`
- `python/anyserve/api_server/__main__.py`
- `python/anyserve/api_server/registry.py`
- `python/anyserve/api_server/router.py`

**任务列表**：

- [x] **1.1 创建 FastAPI 应用骨架**
  - 文件：`python/anyserve/api_server/__main__.py`
  - 实现：FastAPI app，启动参数 --port

- [x] **1.2 实现 Capability 注册表**
  - 文件：`python/anyserve/api_server/registry.py`
  - 数据结构：`Dict[str, List[ReplicaInfo]]`
  - 方法：`register()`, `unregister()`, `lookup()`, `list_all()`

- [x] **1.3 实现注册接口**
  - `POST /register` - Replica 启动时调用
  - `DELETE /unregister` - Replica 停止时调用
  - `GET /registry` - 查询当前注册表

- [x] **1.4 实现路由转发**
  - `POST /infer` - 接收请求，根据 Header 中的 Capability 路由
  - 转发到对应 Replica 的 gRPC 端口

- [x] **1.5 编写测试**
  - 单元测试：registry 逻辑
  - 集成测试：API 接口

---

### Phase 2：Capability 路由

**目标**：将 model name 路由改为 Capability key-value 路由

**修改文件**：
- `cpp/server/model_registry.{cpp,hpp}` → 重命名/改造为 capability_registry
- `python/anyserve/kserve.py` - 添加 `@app.capability` 装饰器
- `python/anyserve/worker/__main__.py` - 注册 capability 而非 model
- `proto/worker_management.proto` - 添加 capability 字段

**任务列表**：

- [x] **2.1 添加 `@app.capability` 装饰器**
  - 文件：`python/anyserve/kserve.py`
  - 语法：`@app.capability(type="chat", model="llama-70b")`
  - 兼容：保留 `@app.model` 作为简化版

- [x] **2.2 修改 Worker 注册逻辑**
  - 文件：`python/anyserve/worker/__main__.py`
  - 改动：注册时发送 capability dict 而非 model_name

- [ ] **2.3 修改 proto 定义** *(MVP 中跳过，Python 层直接实现)*
  - 文件：`proto/worker_management.proto`
  - 添加：`map<string, string> capabilities` 字段

- [ ] **2.4 修改 C++ ModelRegistry** *(MVP 中跳过，Python 层直接实现)*
  - 文件：`cpp/server/model_registry.{cpp,hpp}`
  - 改动：支持 capability key-value 匹配
  - 可选：重命名为 CapabilityRegistry

- [x] **2.5 Replica 向 API Server 注册**
  - 修改 CLI：添加 `--api-server` 参数
  - 启动时：向 API Server POST /register

- [x] **2.6 更新示例**
  - 文件：`examples/mvp_demo/` 目录
  - 改动：使用 `@app.capability` 装饰器

---

### Phase 3：Object System（文件版）

**目标**：实现简化版 Object System，基于共享文件系统

**新建文件**：
- `python/anyserve/objects/__init__.py`
- `python/anyserve/objects/store.py`

**任务列表**：

- [x] **3.1 实现 ObjectStore 类**
  - 文件：`python/anyserve/objects/store.py`
  - 方法：`create(data, key=None) → obj_ref`
  - 方法：`get(obj_ref) → data`
  - 方法：`delete(obj_ref)`
  - 配置：`--object-store /tmp/anyserve-objects`

- [x] **3.2 实现 ObjRef 类**
  - 属性：`path`, `key`, `size`, `created_at`
  - 序列化：可以作为字符串传递

- [x] **3.3 集成到 Worker Context**
  - 修改：`python/anyserve/worker/__main__.py`
  - Handler 签名：`def handler(request, context)`
  - Context 包含：`context.objects` (ObjectStore 实例)

- [x] **3.4 实现 anyserve.call()**
  - 文件：`python/anyserve/kserve.py` (Context.call 方法)
  - 功能：调用其他 Replica，自动传递 obj_ref

- [x] **3.5 编写示例**
  - 文件：`examples/mvp_demo/chat_app.py`
  - 演示：跨 Replica 传递 Object

---

### Phase 4：Delegation

**目标**：实现请求转发机制

**修改文件**：
- `cpp/server/anyserve_dispatcher.cpp` - 添加 delegation 逻辑
- `python/anyserve/api_server/router.py` - 处理 delegation 请求

**任务列表**：

- [ ] **4.1 Dispatcher 检测无法处理的请求** *(MVP 中跳过，API Server 层实现)*
  - 文件：`cpp/server/anyserve_dispatcher.cpp`
  - 逻辑：lookup 失败 → 触发 delegation

- [ ] **4.2 Dispatcher 发起 Delegation** *(MVP 中跳过，API Server 层实现)*
  - 构造新请求，添加 Header：`X-Delegated-From: replica-id`
  - 发送到 API Server

- [x] **4.3 API Server 处理 Delegation**
  - 文件：`python/anyserve/api_server/router.py`
  - 逻辑：排除原始 Replica，重新路由

- [x] **4.4 防止无限循环**
  - 限制：最多 delegation 一次
  - Header：`X-Delegation-Depth: 1`

- [x] **4.5 编写测试**
  - 场景：请求到错误 Replica → delegation → 正确 Replica

---

### Phase 5：Worker 动态管理

**目标**：实现 Worker 的动态启停

**修改文件**：
- `cpp/server/process_supervisor.cpp` - 完善进程管理
- `python/anyserve/worker/__main__.py` - 添加生命周期钩子

**任务列表**：

- [ ] **5.1 完善 ProcessSupervisor**
  - 文件：`cpp/server/process_supervisor.cpp`
  - 功能：启动、停止、健康检查

- [ ] **5.2 实现 Worker Manager**
  - 新建：`cpp/server/worker_manager.{cpp,hpp}`
  - 功能：管理多个 Worker，感知状态

- [ ] **5.3 Worker 资源声明**
  - 语法：`@app.capability(type="chat", gpus=2)`
  - 注册时上报资源需求

- [ ] **5.4 实现 Worker 类（可选）**
  - 文件：`python/anyserve/worker/base.py`
  - 生命周期：`on_start()`, `on_stop()`

- [ ] **5.5 动态启停演示**
  - 场景：根据请求动态启动 Worker
  - 场景：空闲时停止 Worker

---

### Phase 6：集成演示

**目标**：端到端演示所有功能

**新建文件**：
- `examples/mvp_demo/` - 完整演示
- `examples/mvp_demo/run_demo.sh` - 一键启动脚本

**任务列表**：

- [x] **6.1 多 Replica 演示**
  - API Server + 3 个 Replica
  - 不同 Capability 分布

- [x] **6.2 Capability 路由演示**
  - 发送不同 Capability 请求
  - 验证路由正确

- [x] **6.3 Delegation 演示**
  - 发送到"错误" Replica
  - 验证自动转发

- [x] **6.4 Object 传递演示**
  - Replica A 创建 Object
  - 调用 Replica B 时传递
  - Replica B 读取 Object

- [x] **6.5 文档**
  - 演示说明：`examples/mvp_demo/README.md`
  - 测试计划：`docs/test-plan.md`

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

```bash
# chat_app.py
@app.capability(type="chat")
def chat_handler(request, context):
    # 创建中间结果
    embedding = compute_embedding(request.inputs["text"])
    obj_ref = context.objects.create(embedding)

    # 调用 embed Replica 做进一步处理
    result = anyserve.call(
        capability={"type": "embed"},
        inputs={"embedding": obj_ref}
    )

    return result
```

### 场景 4：Worker 动态启停

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

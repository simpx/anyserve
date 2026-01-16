# AnyServe API Server (MVP)

独立的 MVP 版本 API Server，用于 capability-based 路由演示。

## 快速开始

### 1. 启动 API Server

```bash
cd api_server
python main.py --port 8080
```

### 2. 注册 Replica (终端 1)

```bash
curl -N -X POST http://localhost:8080/register -H "Content-Type: application/json" -d '{"replica_id":"r1","endpoint":"localhost:50051","capabilities":[{"model":"qwen2"}]}'
```

保持这个连接，Ctrl+C 断开后 Replica 会被自动清理。

### 3. 查询路由 (终端 2)

```bash
curl http://localhost:8080/route?model=qwen2
```

返回:
```json
{"endpoint":"localhost:50051","replica_id":"r1"}
```

### 4. 查看注册表

```bash
curl http://localhost:8080/registry
```

### 5. 断开注册 (终端 1 按 Ctrl+C)，再查询

```bash
curl http://localhost:8080/route?model=qwen2
```

返回 404:
```json
{"detail":"no matching replica"}
```

## API 接口

### POST /register

注册 Replica，返回 SSE 长连接。断开时自动清理。

```bash
curl -N -X POST http://localhost:8080/register -H "Content-Type: application/json" -d '{"replica_id":"r1","endpoint":"localhost:50051","capabilities":[{"model":"qwen2"},{"model":"llama","type":"chat"}]}'
```

响应 (SSE 流):
```
data: {"status": "registered", "replica_id": "r1"}
data: {"status": "alive"}
data: {"status": "alive"}
...
```

### GET /route

查询匹配 capability 的路由。

```bash
# 单条件查询
curl "http://localhost:8080/route?model=qwen2"

# 多条件查询
curl "http://localhost:8080/route?model=llama&type=chat"
```

响应 (200):
```json
{"endpoint":"localhost:50051","replica_id":"r1"}
```

响应 (404):
```json
{"detail":"no matching replica"}
```

### GET /registry

列出所有注册的 Replicas。

```bash
curl http://localhost:8080/registry
```

响应:
```json
{"replicas":[{"replica_id":"r1","endpoint":"localhost:50051","capabilities":[{"model":"qwen2"}]}]}
```

### GET /health

健康检查。

```bash
curl http://localhost:8080/health
```

## 匹配规则

- Query params 构成查询条件
- 查询条件必须是 Replica capabilities 的**子集**才匹配
- 多个匹配时随机选择（简单负载均衡）

示例:

```
Replica 注册: capabilities = [{"model":"qwen2","type":"chat"}]

?model=qwen2           -> 匹配 (子集)
?type=chat             -> 匹配 (子集)
?model=qwen2&type=chat -> 匹配 (相等)
?model=qwen3           -> 不匹配 (值不同)
?model=qwen2&gpu=1     -> 不匹配 (gpu 不存在)
```

## 多 Replica 测试

```bash
# 终端 1: 启动 API Server
python main.py --port 8080

# 终端 2: 注册 Replica A (chat)
curl -N -X POST http://localhost:8080/register -H "Content-Type: application/json" -d '{"replica_id":"a","endpoint":"localhost:50051","capabilities":[{"type":"chat"}]}'

# 终端 3: 注册 Replica B (embed)
curl -N -X POST http://localhost:8080/register -H "Content-Type: application/json" -d '{"replica_id":"b","endpoint":"localhost:50052","capabilities":[{"type":"embed"}]}'

# 终端 4: 测试路由
curl "http://localhost:8080/route?type=chat"   # -> localhost:50051
curl "http://localhost:8080/route?type=embed"  # -> localhost:50052
curl http://localhost:8080/registry            # -> 两个 replica
```

## 架构

```
控制链路 (HTTP):
  Dispatcher ──POST /register──> API Server (SSE 长连接)
  Client ──────GET /route──────> API Server

数据链路 (gRPC):
  Client ──────gRPC────────────> Dispatcher ──> Worker
  (MVP: API Server 不参与数据链路，Client 直连 Dispatcher)
```

## 文件结构

```
api_server/
├── main.py         # FastAPI 入口
├── registry.py     # Capability 注册表
└── README.md       # 本文档
```

## Client 集成

Client 类支持 **Discovery 模式**，通过 API Server 自动发现 Worker 端点：

```python
from anyserve.worker.client import Client

# Discovery 模式 - 通过 API Server 发现 Worker
client = Client(
    api_server="http://localhost:8080",
    capability={"type": "chat"}
)

# 调用推理（自动发现并连接到匹配的 Worker）
result = client.infer(
    model_name="chat",
    inputs={"prompt": ["Hello, world!"]}
)

# 查看发现的端点
print(f"Endpoint: {client.endpoint}")      # "localhost:50051"
print(f"Replica ID: {client.replica_id}")  # "replica-a"

client.close()
```

### Discovery 流程

```
Client                           API Server              Worker
  │                                  │                      │
  │ GET /route?type=chat             │                      │
  │ ─────────────────────────────────>                      │
  │                                  │                      │
  │ {"endpoint": "localhost:50051"}  │                      │
  │ <─────────────────────────────────                      │
  │                                  │                      │
  │ gRPC ModelInfer                                         │
  │ ─────────────────────────────────────────────────────────>
  │                                  │                      │
  │ ModelInferResponse                                      │
  │ <─────────────────────────────────────────────────────────
  │                                  │                      │
```

### 失败重试

在 Discovery 模式下，如果推理失败，Client 会自动重新发现端点并重试：

```python
client = Client(
    api_server="http://localhost:8080",
    capability={"type": "chat"}
)

# retry_on_failure=True (默认) 时，失败会触发重新发现
result = client.infer("chat", inputs, retry_on_failure=True)
```

详细使用示例请参阅 [examples/multiserver/](../examples/multiserver/)。

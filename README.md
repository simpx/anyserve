# anyserve

面向大规模 LLM 推理的 Serving Runtime。

## 项目状态

**POC 阶段** - 核心骨架已实现，正在开发 MVP 功能。

## 核心特性

- **Capability 驱动**：基于任意 key-value 的请求路由，而非固定 model name
- **Worker 动态启停**：根据负载动态管理 Worker，资源灵活复用
- **控制流/数据流分离**：控制流走 KServe 协议，数据流走 Object System
- **C++ Dispatcher + Python Worker**：高性能控制面 + 灵活执行面

## 架构概览

```
┌──────────────────────────────────────────┐
│            API Server (独立项目)          │
│         基于 Capability 路由请求          │
└──────────────────────┬───────────────────┘
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Replica A   │ │  Replica B   │ │  Replica C   │
│  (anyserve)  │ │  (anyserve)  │ │  (anyserve)  │
│              │ │              │ │              │
│ Dispatcher   │ │ Dispatcher   │ │ Dispatcher   │
│     ↓        │ │     ↓        │ │     ↓        │
│  Workers     │ │  Workers     │ │  Workers     │
└──────────────┘ └──────────────┘ └──────────────┘
```

详细设计请参阅：
- [架构设计](docs/architecture.md) - 概念、原则、分层
- [运行时实现](docs/runtime.md) - 代码结构、协议、流程
- [MVP 计划](docs/mvp.md) - 开发目标和任务列表

## 快速开始

### 环境要求

- Python 3.11+
- C++ 编译器（支持 C++17）
- CMake 3.20+
- Conan 2.0+

### 安装

```bash
# 安装依赖并构建
just setup
just build

# 安装 Python 包
pip install -e python/
```

### 运行示例

```bash
# 启动 server
anyserve examples.basic.app:app --port 8000 --workers 1

# 测试
python examples/basic/run_example.py
```

### 定义 Capability Handler

```python
from anyserve import AnyServe, ModelInferRequest, ModelInferResponse

app = AnyServe()

@app.capability(type="echo")
def echo_handler(request: ModelInferRequest) -> ModelInferResponse:
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

### Client 连接模式

Client 支持两种连接模式：

```python
from anyserve.worker.client import Client

# Direct 模式 - 直接连接指定 Worker
client = Client(endpoint="localhost:50051")

# Discovery 模式 - 通过 API Server 自动发现 Worker
client = Client(
    api_server="http://localhost:8080",
    capability={"type": "echo"}
)

result = client.infer("echo", {"text": ["hello"]})
client.close()
```

详见 [examples/multiserver/](examples/multiserver/) 示例。

## 项目结构

```
anyserve/
├── cpp/                    # C++ Dispatcher
│   └── server/             # 核心组件
├── python/anyserve/        # Python Worker
│   ├── cli.py              # CLI 入口
│   ├── kserve.py           # KServe 协议
│   └── worker/             # Worker 实现
├── proto/                  # 协议定义
├── examples/               # 示例
└── docs/                   # 文档
    ├── architecture.md     # 架构设计
    ├── runtime.md          # 运行时实现
    └── mvp.md              # MVP 计划
```

## 开发

```bash
just setup    # 安装依赖
just build    # 构建
just clean    # 清理
```

## 文档

| 文档 | 内容 |
|------|------|
| [architecture.md](docs/architecture.md) | 架构设计、核心概念、设计原则 |
| [runtime.md](docs/runtime.md) | 实现细节、代码结构、协议 |
| [mvp.md](docs/mvp.md) | MVP 目标、当前状态、开发计划 |
| [agents.md](agents.md) | AI 助手协作指南 |

## License

[待定]

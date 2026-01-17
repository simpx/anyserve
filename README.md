# anyserve

面向大规模 LLM 推理的 Serving Runtime。

## 项目状态

**POC 阶段** - 核心骨架已实现，正在开发 MVP 功能。

## 核心特性

- **Capability 驱动**：基于任意 key-value 的请求路由，而非固定 model name
- **Worker 动态启停**：根据负载动态管理 Worker，资源灵活复用
- **控制流/数据流分离**：控制流走 KServe 协议，数据流走 Object System
- **C++ Agent + Python Worker**：高性能控制面 + 灵活执行面

## 核心概念

### Capability

Capability 是 anyserve 的核心抽象，使用任意 key-value 描述服务能力：

```
{type: "chat", model: "llama-70b"}
{type: "embed"}
```

### Agent

Agent 是 anyserve 的主进程（每机一个），负责：
- 流量入口（KServe gRPC）
- Worker 管理（启动、停止、健康检查）
- 请求队列（按 Capability 分队列）
- Object System（跨实例数据传递）

### Worker

Worker 是执行实际推理的进程：
- 1 Worker 提供 1 组 Capability
- 通过 `@app.capability()` 装饰器定义

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
│    Agent     │ │    Agent     │ │    Agent     │
│     ↓        │ │     ↓        │ │     ↓        │
│  Workers     │ │  Workers     │ │  Workers     │
└──────────────┘ └──────────────┘ └──────────────┘
```

详细设计请参阅：
- [架构设计](docs/architecture.md) - 概念、原则、分层
- [运行时实现](docs/runtime.md) - 代码结构、协议、流程
- [MVP 计划](docs/mvp.md) - 开发目标和任务列表

## 安装

```bash
pip install -e .
```

## 用法

anyserve 提供两种使用方式：

### 1. `anyserve run` - 运行自定义 Worker

适用于自定义推理逻辑的场景。

```bash
anyserve run examples.basic.app:app --port 8000 --workers 1
```

#### 定义 Worker - 直接方式

使用 `app = AnyServe()` 直接定义：

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

#### 定义 Worker - Factory 方式

当需要在 Worker 启动时初始化资源（如加载模型）时，使用 factory 模式：

```python
# myapp.py
from anyserve import AnyServe, ModelInferRequest, ModelInferResponse

def create_app():
    """Factory 函数 - 每个 Worker 进程调用一次"""
    app = AnyServe()

    # 初始化资源（如加载模型）
    model = load_my_model()

    @app.capability(type="inference")
    def inference_handler(request: ModelInferRequest) -> ModelInferResponse:
        # 使用已加载的 model
        result = model.predict(...)
        return build_response(result)

    return app
```

运行时添加 `--factory` 参数：

```bash
anyserve run myapp:create_app --factory --port 8000 --workers 2
```

### 2. `anyserve serve` - 内置 LLM 服务

直接指定 GGUF 模型权重，使用内置的 llama.cpp 引擎：

```bash
# 基础用法
anyserve serve /path/to/model.gguf --name my-model --port 8000

# 同时启用 OpenAI 兼容 API
anyserve serve /path/to/model.gguf --name my-model --port 8000 --openai-port 8080

# 完整参数
anyserve serve /path/to/model.gguf \
    --name my-model \
    --n-ctx 4096 \
    --n-gpu-layers -1 \
    --port 8000 \
    --openai-port 8080
```

这将暴露：
- **KServe gRPC**: `localhost:8000` - 原生协议
- **OpenAI API**: `localhost:8080` - 兼容 OpenAI SDK

详见 [llamacpp 文档](docs/llamacpp.md)。

## 示例

| 示例 | 说明 | 演示特性 |
|------|------|---------|
| [basic/](examples/basic/) | 基础用法 | echo、add handler |
| [streaming/](examples/streaming/) | 流式推理 | Server Streaming |
| [pipeline/](examples/pipeline/) | Worker 间协作 | context.call() |
| [multi_server/](examples/multi_server/) | 多服务发现 | Discovery Mode |
| [llamacpp/](examples/llamacpp/) | LLM 服务 | llama.cpp + OpenAI API |

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

详见 [examples/multi_server/](examples/multi_server/) 示例。

### Worker 间调用 (context.call)

Worker 可以通过 `context.call()` 调用其他服务，构建处理流水线：

```python
@app.capability(type="tokenize")
def handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
    # 处理输入
    text = request.get_input("text").bytes_contents[0].decode()
    tokens = tokenize(text)

    # 调用其他服务
    result = context.call(
        model_name="analyze",
        capability={"type": "analyze"},  # 通过 API Server 路由
        inputs={"tokens": [",".join(tokens)]}
    )

    return build_response(result)
```

详见 [examples/pipeline/](examples/pipeline/) 示例。

## 项目结构

```
anyserve/
├── python/anyserve/        # Python 包
│   ├── cli/                # CLI 入口
│   ├── kserve.py           # KServe 协议
│   ├── worker/             # Worker 实现
│   └── builtins/           # 内置引擎 (llamacpp)
├── api_server/             # API Server
├── proto/                  # 协议定义
├── examples/               # 示例
│   ├── basic/              # 基础用法
│   ├── streaming/          # 流式推理
│   ├── pipeline/           # Worker 间协作
│   ├── multi_server/       # 多服务发现
│   └── llamacpp/           # LLM 服务
└── docs/                   # 文档
```

## 文档

| 文档 | 内容 |
|------|------|
| [architecture.md](docs/architecture.md) | 架构设计、核心概念、设计原则 |
| [runtime.md](docs/runtime.md) | 实现细节、代码结构、协议 |
| [mvp.md](docs/mvp.md) | MVP 目标、当前状态、开发计划 |
| [llamacpp.md](docs/llamacpp.md) | llama.cpp 内置引擎使用指南 |

## License

[待定]

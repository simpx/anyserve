# AnyServe

面向大规模 LLM 推理的 Capability-Oriented Serving Runtime（PoC）。采用 Rust 控制路径 + Python 执行路径的混合架构，用最小实现验证 capability 路由与委托机制。

## 文档

- [架构总览](docs/architecture.md)：三层边界、核心抽象、委托与 Object Plane。
- [MVP 范围](docs/mvp.md)：PoC 目标、非目标、验收标准。
- [agents.md](agents.md)：AI Agent 协作指南。

## 核心概念

- Capability First：以语义能力（如 decode、decode.heavy）为路由与编排单位。
- Replica as Runtime：不可拆分的执行单元（Rust runtime + Python workers），对调度器透明。
- Delegation：本地硬不匹配时升级 capability 并交由调度器重新路由，最多一次委托。

## 目录结构

- python/anyserve/：FastAPI 控制面与 Python handlers。
- src/：Rust runtime（请求接入、调度、IPC）。
- docs/：项目文档（架构与 MVP）。
- agents.md：AI Agent 协作指南。

## 快速开始

环境要求：Python 3.11+、Rust (Cargo)。

### 1. 安装

```bash
# 安装 Python 库 (anyserve_worker)
pip install -e .

# 安装 CLI 工具 (anyserve)
cargo install --path .
```

### 2. 定义应用 (python)

创建一个 Python 文件 (例如 `app.py`):

```python
from anyserve_worker import Worker, ModelInferResponse

app = Worker()

@app.model("my_model")
def impl(request):
    print(f"Handling request for {request.model_name}")
    return ModelInferResponse(model_name=request.model_name)
```

### 3. 启动服务

使用 `anyserve` 命令行工具启动：

```bash
# 格式: anyserve <module>:<variable>
anyserve app:app --port 8080
```

### 4. 客户端调用

使用内置 Client 进行交互：

```python
from anyserve_worker import Client

client = Client("localhost:8080")
if client.is_alive():
    result = client.infer("my_model", inputs={"input_1": [1, 2, 3]})
    print(result)
```

## 老版本快速开始 (Dev Mode)

1) 初始化环境（如需安装 Rust/just）：
```bash
./scripts/bootstrap.sh
```

2) 安装 Python 依赖：
```bash
uv sync
```

3) 开发模式运行：
```bash
just run
```

如需重新构建 Rust 扩展：
```bash
uv run maturin develop
```

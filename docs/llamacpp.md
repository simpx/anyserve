# llama.cpp Worker 实现指南

## 概述

本文档描述如何在 anyserve 中实现一个内置的 llama.cpp worker。该 worker 使用 `llama-cpp-python` 库,支持运行 GGUF 格式的 LLM 模型。

### 设计原则

1. **内置 Worker**: 作为 anyserve 预置的 worker 实现,用户无需编写代码
2. **与用户 Worker 一致**: `anyserve serve` 本质上只是使用内置 worker 并预配置参数,底层运行机制和用户自定义 worker 完全一致
3. **可配置**: 通过命令行参数和配置文件控制模型加载和生成参数
4. **最小耦合 (v1)**: 第一版与 anyserve 核心无深度耦合,便于独立开发
5. **渐进增强**: 未来版本可增加与 anyserve 的深度集成

### 架构说明

`anyserve serve` 命令的本质:

```
anyserve serve /models/model.gguf --name my-model
```

等价于用户自己编写一个 worker 并运行:

```python
# 用户自定义 worker 的写法
from anyserve import AnyServe
from anyserve.builtins.llamacpp import LlamaCppEngine

app = AnyServe()
engine = LlamaCppEngine(model_path="/models/model.gguf")
engine.load()

@app.capability(type="completion", model="my-model")
def completion_handler(request, context):
    prompt = extract_prompt(request)
    return engine.generate(prompt)

# 使用 anyserve 运行
# anyserve app:app
```

`anyserve serve` 只是将这个过程封装成命令行,让用户无需编写代码即可运行 llama.cpp 模型。

## 使用方式

### 命令行启动

```bash
# 最简单的方式 - 直接指定模型路径
anyserve serve /models/llama-7b-chat.gguf

# 指定模型名称 (用于 API 调用时的 model_name)
anyserve serve /models/llama-7b-chat.gguf --name llama-7b

# 完整参数示例
anyserve serve /models/llama-7b-chat.gguf \
    --name llama-7b \
    --n-ctx 4096 \
    --n-gpu-layers 35 \
    --port 8000

# 使用配置文件
anyserve serve --config /etc/anyserve/model.yaml
```

### 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model_path` | str | (位置参数) | GGUF 模型文件路径 |
| `--name` | str | 从文件名推断 | 模型名称,用于 API 调用 |
| `--n-ctx` | int | 2048 | 上下文窗口大小 |
| `--n-gpu-layers` | int | -1 | GPU 层数,-1 表示全部 |
| `--n-batch` | int | 512 | 批处理大小 |
| `--n-threads` | int | auto | CPU 线程数 |
| `--port` | int | 8000 | 服务端口 |
| `--config` | str | - | YAML 配置文件路径 |

### 配置文件格式

```yaml
# model.yaml
model_path: /models/llama-7b-chat.gguf
name: llama-7b

# 模型加载参数
n_ctx: 4096
n_gpu_layers: 35
n_batch: 512
n_threads: 8

# 生成参数默认值
max_tokens: 256
temperature: 0.7
top_p: 0.95
top_k: 40
repeat_penalty: 1.1

# 服务参数
port: 8000
```

## 实现

### 目录结构

```
python/anyserve/
├── cli/
│   ├── __init__.py
│   ├── main.py              # CLI 入口点
│   └── serve.py             # serve 子命令实现
├── builtins/
│   └── llamacpp/
│       ├── __init__.py
│       ├── config.py        # 配置类定义
│       ├── engine.py        # llama.cpp 引擎封装
│       └── handlers.py      # 请求处理器
```

### CLI 入口 (`cli/main.py`)

```python
import click
from .serve import serve_command


@click.group()
def cli():
    """anyserve - LLM serving runtime"""
    pass


cli.add_command(serve_command, name="serve")


def main():
    cli()


if __name__ == "__main__":
    main()
```

### serve 子命令 (`cli/serve.py`)

```python
import click
from pathlib import Path
from anyserve.builtins.llamacpp import LlamaCppConfig, create_server


@click.command()
@click.argument("model_path", type=click.Path(exists=True), required=False)
@click.option("--name", type=str, help="Model name for API")
@click.option("--n-ctx", type=int, default=2048, help="Context window size")
@click.option("--n-gpu-layers", type=int, default=-1, help="GPU layers (-1 for all)")
@click.option("--n-batch", type=int, default=512, help="Batch size")
@click.option("--n-threads", type=int, default=None, help="CPU threads")
@click.option("--port", type=int, default=8000, help="Server port")
@click.option("--config", type=click.Path(exists=True), help="Config file path")
def serve_command(model_path, name, n_ctx, n_gpu_layers, n_batch, n_threads, port, config):
    """Start anyserve with a llama.cpp model.

    Example:
        anyserve serve /models/llama-7b.gguf --name llama-7b --port 8000
    """
    # 加载配置
    if config:
        cfg = LlamaCppConfig.from_yaml(config)
    else:
        if not model_path:
            raise click.UsageError("Either model_path or --config is required")

        # 从文件名推断模型名称
        model_name = name or Path(model_path).stem

        cfg = LlamaCppConfig(
            model_path=model_path,
            name=model_name,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            n_threads=n_threads,
            port=port,
        )

    cfg.validate()

    click.echo(f"Starting anyserve with model: {cfg.model_path}")
    click.echo(f"  Model name: {cfg.name}")
    click.echo(f"  Context size: {cfg.n_ctx}")
    click.echo(f"  GPU layers: {cfg.n_gpu_layers}")
    click.echo(f"  Port: {cfg.port}")

    # 创建并启动服务器
    server = create_server(cfg)
    server.run()
```

### 配置类 (`builtins/llamacpp/config.py`)

```python
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import yaml


@dataclass
class LlamaCppConfig:
    """llama.cpp 内置 Worker 配置"""

    # 模型路径 (必需)
    model_path: str = ""

    # 模型名称 (用于 API)
    name: str = "default"

    # 模型加载参数
    n_ctx: int = 2048
    n_gpu_layers: int = -1
    n_batch: int = 512
    n_threads: Optional[int] = None

    # 生成参数默认值
    max_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 0.95
    top_k: int = 40
    repeat_penalty: float = 1.1
    stop: list[str] = field(default_factory=list)

    # 服务参数
    port: int = 8000

    @classmethod
    def from_yaml(cls, path: str) -> "LlamaCppConfig":
        """从 YAML 文件加载配置"""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def validate(self) -> None:
        """验证配置有效性"""
        if not self.model_path:
            raise ValueError("model_path is required")
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        if self.n_ctx < 1:
            raise ValueError("n_ctx must be positive")
        if self.port < 1 or self.port > 65535:
            raise ValueError("port must be between 1 and 65535")
```

### llama.cpp 引擎封装 (`builtins/llamacpp/engine.py`)

```python
from llama_cpp import Llama
from typing import Iterator, Optional
from .config import LlamaCppConfig


class LlamaCppEngine:
    """llama.cpp 引擎封装"""

    def __init__(self, config: LlamaCppConfig):
        self.config = config
        self._model: Optional[Llama] = None

    def load(self) -> None:
        """加载模型"""
        self._model = Llama(
            model_path=self.config.model_path,
            n_ctx=self.config.n_ctx,
            n_gpu_layers=self.config.n_gpu_layers,
            n_batch=self.config.n_batch,
            n_threads=self.config.n_threads,
            verbose=False,
        )

    @property
    def model(self) -> Llama:
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")
        return self._model

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        stop: Optional[list[str]] = None,
    ) -> str:
        """生成文本 (非流式)"""
        result = self.model(
            prompt,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=top_p if top_p is not None else self.config.top_p,
            top_k=top_k if top_k is not None else self.config.top_k,
            repeat_penalty=repeat_penalty if repeat_penalty is not None else self.config.repeat_penalty,
            stop=stop or self.config.stop or None,
            echo=False,
        )
        return result["choices"][0]["text"]

    def generate_stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        stop: Optional[list[str]] = None,
    ) -> Iterator[str]:
        """生成文本 (流式)"""
        for chunk in self.model(
            prompt,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=top_p if top_p is not None else self.config.top_p,
            top_k=top_k if top_k is not None else self.config.top_k,
            repeat_penalty=repeat_penalty if repeat_penalty is not None else self.config.repeat_penalty,
            stop=stop or self.config.stop or None,
            echo=False,
            stream=True,
        ):
            yield chunk["choices"][0]["text"]
```

### 请求处理器 (`builtins/llamacpp/handlers.py`)

```python
from anyserve import AnyServe
from anyserve.proto.grpc_predict_v2_pb2 import (
    ModelInferRequest,
    ModelInferResponse,
    ModelStreamInferResponse,
)
from .config import LlamaCppConfig
from .engine import LlamaCppEngine


def create_handlers(app: AnyServe, config: LlamaCppConfig, engine: LlamaCppEngine):
    """注册请求处理器到 AnyServe 应用"""

    @app.capability(type="completion", model=config.name)
    def completion_handler(request: ModelInferRequest, context) -> ModelInferResponse:
        """处理文本补全请求 (非流式)"""
        prompt = _extract_prompt(request)
        params = _extract_generation_params(request)

        generated_text = engine.generate(prompt, **params)

        return _build_response(request, generated_text, config.name)

    @app.capability(type="completion", model=config.name, stream=True)
    def completion_stream_handler(request: ModelInferRequest, context, stream) -> None:
        """处理文本补全请求 (流式)"""
        prompt = _extract_prompt(request)
        params = _extract_generation_params(request)

        for token in engine.generate_stream(prompt, **params):
            response = _build_stream_response(request, token, config.name, is_last=False)
            stream.send(response)

        final_response = _build_stream_response(request, "", config.name, is_last=True)
        stream.send(final_response)


def _extract_prompt(request: ModelInferRequest) -> str:
    """从请求中提取 prompt"""
    for inp in request.inputs:
        if inp.name in ("prompt", "text_input"):
            if inp.contents.bytes_contents:
                return inp.contents.bytes_contents[0].decode("utf-8")
    raise ValueError("No prompt found in request. Expected 'prompt' or 'text_input' input.")


def _extract_generation_params(request: ModelInferRequest) -> dict:
    """从请求中提取生成参数"""
    params = {}
    param_mapping = {
        "max_tokens": int,
        "temperature": float,
        "top_p": float,
        "top_k": int,
        "repeat_penalty": float,
    }

    for inp in request.inputs:
        if inp.name in param_mapping:
            converter = param_mapping[inp.name]
            if inp.contents.int64_contents:
                params[inp.name] = converter(inp.contents.int64_contents[0])
            elif inp.contents.fp32_contents:
                params[inp.name] = converter(inp.contents.fp32_contents[0])

    # 提取 stop sequences
    for inp in request.inputs:
        if inp.name == "stop":
            if inp.contents.bytes_contents:
                params["stop"] = [s.decode("utf-8") for s in inp.contents.bytes_contents]

    return params


def _build_response(request: ModelInferRequest, text: str, model_name: str) -> ModelInferResponse:
    """构建非流式响应"""
    return ModelInferResponse(
        model_name=model_name,
        id=request.id,
        outputs=[
            ModelInferResponse.InferOutputTensor(
                name="text_output",
                datatype="BYTES",
                shape=[1],
                contents=ModelInferResponse.InferTensorContents(
                    bytes_contents=[text.encode("utf-8")]
                )
            )
        ]
    )


def _build_stream_response(
    request: ModelInferRequest,
    token: str,
    model_name: str,
    is_last: bool
) -> ModelStreamInferResponse:
    """构建流式响应"""
    return ModelStreamInferResponse(
        error_message="",
        infer_response=ModelInferResponse(
            model_name=model_name,
            id=request.id,
            outputs=[
                ModelInferResponse.InferOutputTensor(
                    name="text_output",
                    datatype="BYTES",
                    shape=[1],
                    contents=ModelInferResponse.InferTensorContents(
                        bytes_contents=[token.encode("utf-8")]
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
```

### 服务器创建 (`builtins/llamacpp/__init__.py`)

```python
from anyserve import AnyServe
from .config import LlamaCppConfig
from .engine import LlamaCppEngine
from .handlers import create_handlers

__all__ = ["LlamaCppConfig", "LlamaCppEngine", "create_server"]


class LlamaCppServer:
    """llama.cpp 内置服务器"""

    def __init__(self, config: LlamaCppConfig):
        self.config = config
        self.app = AnyServe()
        self.engine = LlamaCppEngine(config)

    def run(self):
        """启动服务器"""
        # 加载模型
        print(f"Loading model from {self.config.model_path}...")
        self.engine.load()
        print("Model loaded successfully.")

        # 注册处理器
        create_handlers(self.app, self.config, self.engine)

        # 启动 anyserve
        # 内部会启动 Agent + Worker 进程
        self.app.serve(port=self.config.port)


def create_server(config: LlamaCppConfig) -> LlamaCppServer:
    """创建 llama.cpp 服务器实例"""
    return LlamaCppServer(config)
```

### pyproject.toml 入口点配置

```toml
[project.scripts]
anyserve = "anyserve.cli.main:main"

[project.optional-dependencies]
llamacpp = [
    "llama-cpp-python>=0.2.0",
    "pyyaml>=6.0",
]
```

## API 规范

### 请求格式

使用 KServe v2 协议的 `ModelInferRequest`:

```json
{
  "model_name": "llama-7b",
  "inputs": [
    {
      "name": "prompt",
      "datatype": "BYTES",
      "shape": [1],
      "contents": {
        "bytes_contents": ["SGVsbG8sIHdvcmxk"]
      }
    },
    {
      "name": "max_tokens",
      "datatype": "INT64",
      "shape": [1],
      "contents": {
        "int64_contents": [256]
      }
    },
    {
      "name": "temperature",
      "datatype": "FP32",
      "shape": [1],
      "contents": {
        "fp32_contents": [0.7]
      }
    }
  ]
}
```

### 响应格式

非流式响应:

```json
{
  "model_name": "llama-7b",
  "id": "request-123",
  "outputs": [
    {
      "name": "text_output",
      "datatype": "BYTES",
      "shape": [1],
      "contents": {
        "bytes_contents": ["R2VuZXJhdGVkIHRleHQ="]
      }
    }
  ]
}
```

流式响应 (每个 chunk):

```json
{
  "error_message": "",
  "infer_response": {
    "model_name": "llama-7b",
    "id": "request-123",
    "outputs": [
      {
        "name": "text_output",
        "datatype": "BYTES",
        "shape": [1],
        "contents": {
          "bytes_contents": ["dG9rZW4="]
        }
      },
      {
        "name": "finish_reason",
        "datatype": "BYTES",
        "shape": [1],
        "contents": {
          "bytes_contents": [""]
        }
      }
    ]
  }
}
```

### 支持的输入参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `prompt` / `text_input` | BYTES | (必需) | 输入文本 |
| `max_tokens` | INT64 | 256 | 最大生成 token 数 |
| `temperature` | FP32 | 0.7 | 采样温度 |
| `top_p` | FP32 | 0.95 | nucleus sampling 参数 |
| `top_k` | INT64 | 40 | top-k sampling 参数 |
| `repeat_penalty` | FP32 | 1.1 | 重复惩罚系数 |
| `stop` | BYTES[] | [] | 停止序列列表 |

## 客户端使用示例

### 使用 anyserve 客户端

```python
from anyserve.client import AnyServeClient

client = AnyServeClient("localhost:8000")

# 非流式调用
response = client.infer(
    model_name="llama-7b",
    inputs={
        "prompt": "Once upon a time",
        "max_tokens": 100,
        "temperature": 0.8,
    }
)
print(response.outputs["text_output"])

# 流式调用
for chunk in client.infer_stream(
    model_name="llama-7b",
    inputs={
        "prompt": "Once upon a time",
        "max_tokens": 100,
    }
):
    print(chunk.outputs["text_output"], end="", flush=True)
```

### 使用 curl

```bash
# 非流式请求
curl -X POST http://localhost:8000/v2/models/llama-7b/infer \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [
      {
        "name": "prompt",
        "datatype": "BYTES",
        "shape": [1],
        "data": ["Once upon a time"]
      }
    ]
  }'

# 流式请求
curl -X POST http://localhost:8000/v2/models/llama-7b/infer_stream \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [
      {
        "name": "prompt",
        "datatype": "BYTES",
        "shape": [1],
        "data": ["Once upon a time"]
      }
    ]
  }'
```

## 依赖安装

```bash
# 安装 anyserve 及 llama.cpp 支持
pip install anyserve[llamacpp]

# 或分别安装
pip install anyserve
pip install llama-cpp-python

# GPU 支持 (CUDA)
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python

# GPU 支持 (Metal/macOS)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python
```

## 未来增强

### Phase 2: Chat 格式支持

```python
# 新增 chat capability
@app.capability(type="chat", model=config.name)
def chat_handler(request: ModelInferRequest, context) -> ModelInferResponse:
    messages = _extract_messages(request)  # [{"role": "user", "content": "..."}]
    prompt = engine.apply_chat_template(messages)
    response = engine.generate(prompt)
    return _build_chat_response(request, response)
```

### Phase 3: 多模型支持

```bash
# 通过配置文件支持多个模型
anyserve serve --config multi-model.yaml
```

```yaml
# multi-model.yaml
models:
  - path: /models/llama-7b.gguf
    name: llama-7b
    n_gpu_layers: 35
  - path: /models/codellama-13b.gguf
    name: codellama
    n_gpu_layers: 40
```

### Phase 4: anyserve 深度集成

- 利用 Agent 的资源感知,动态调整 `n_gpu_layers`
- 基于请求队列深度调整 batch 策略
- 支持模型热切换 (unload/load)
- 集成 Object System 用于大型输入传递

## 测试

### 单元测试

```python
# tests/builtins/test_llamacpp_config.py
import pytest
from anyserve.builtins.llamacpp import LlamaCppConfig


def test_config_validation_missing_path():
    config = LlamaCppConfig(model_path="")
    with pytest.raises(ValueError, match="model_path is required"):
        config.validate()


def test_config_validation_invalid_port():
    config = LlamaCppConfig(model_path="/tmp/model.gguf", port=0)
    with pytest.raises(ValueError, match="port must be between"):
        config.validate()


def test_config_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
model_path: /models/test.gguf
name: test-model
n_ctx: 4096
port: 9000
""")

    config = LlamaCppConfig.from_yaml(str(config_file))
    assert config.model_path == "/models/test.gguf"
    assert config.name == "test-model"
    assert config.n_ctx == 4096
    assert config.port == 9000
```

### 集成测试

```python
# tests/integration/test_llamacpp_server.py
import pytest
from anyserve.builtins.llamacpp import LlamaCppConfig, create_server


@pytest.fixture
def server(test_model_path):
    config = LlamaCppConfig(
        model_path=test_model_path,
        name="test",
        n_ctx=512,
        port=8888,
    )
    return create_server(config)


@pytest.mark.skipif(not has_test_model(), reason="No test model available")
def test_server_generation(server):
    # 启动服务器 (后台)
    server.engine.load()

    # 测试生成
    result = server.engine.generate("Hello", max_tokens=10)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.skipif(not has_test_model(), reason="No test model available")
def test_server_streaming(server):
    server.engine.load()

    tokens = list(server.engine.generate_stream("Hello", max_tokens=10))
    assert len(tokens) > 0
```

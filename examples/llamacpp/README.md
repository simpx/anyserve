# LlamaCpp Serve Example

This example shows how to serve a GGUF model using `anyserve serve` with the native KServe gRPC protocol, and optionally use the OpenAI-compatible API server for REST access.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     OpenAI Clients                          │
│              (curl, Python openai lib, etc.)                │
└─────────────────────────────────────────────────────────────┘
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    openai_server                            │
│           (OpenAI → KServe protocol converter)              │
│                    Port 8080 (optional)                     │
└─────────────────────────────────────────────────────────────┘
                              │ gRPC (KServe v2)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      AnyServe                               │
│   ┌─────────────────────────────────────────────────────┐   │
│   │            C++ Dispatcher (gRPC :8000)              │   │
│   └─────────────────────────────────────────────────────┘   │
│                          │ Unix Socket                      │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              Python Worker                          │   │
│   │   @app.capability(type="generate")                  │   │
│   │   @app.capability(type="generate_stream")           │   │
│   │              LlamaCppEngine                         │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. Install anyserve with llama.cpp support:
```bash
pip install -e ".[llamacpp]"
# Or install dependencies manually:
pip install llama-cpp-python pyyaml pydantic
```

2. Download a GGUF model:
```bash
# Example: TinyLlama 1.1B (smallest practical model, ~500MB)
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q2_K.gguf
```

## Quick Start

### 1. Start AnyServe with the model (KServe gRPC)

```bash
anyserve serve tinyllama-1.1b-chat-v1.0.Q2_K.gguf --name tinyllama --port 8000

# Or with more options
anyserve serve tinyllama-1.1b-chat-v1.0.Q2_K.gguf \
    --name tinyllama \
    --n-ctx 2048 \
    --n-gpu-layers -1 \
    --port 8000 \
    --workers 1
```

This exposes the model via gRPC on port 8000 using the KServe v2 inference protocol.

### 2. (Optional) Start OpenAI-compatible API server

```bash
python -m openai_server --anyserve-endpoint localhost:8000 --port 8080
```

This provides an OpenAI-compatible REST API on port 8080.

## API Usage

### Direct gRPC (KServe v2 protocol)

Use any KServe v2 compatible client. The model exposes these capabilities:
- `type="generate"` - Non-streaming text generation
- `type="generate_stream"` - Streaming text generation
- `type="model_info"` - Get model information

### OpenAI-compatible REST API (via openai_server)

#### List Models
```bash
curl http://localhost:8080/v1/models
```

#### Text Completion
```bash
curl -X POST http://localhost:8080/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "prompt": "Once upon a time",
        "max_tokens": 100,
        "temperature": 0.7
    }'
```

#### Streaming Completion
```bash
curl -X POST http://localhost:8080/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "prompt": "Once upon a time",
        "max_tokens": 100,
        "stream": true
    }'
```

#### Chat Completion
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "max_tokens": 100
    }'
```

## Configuration File

You can also use a YAML configuration file:

```yaml
# model.yaml
model_path: /models/tinyllama-1.1b-chat-v1.0.Q2_K.gguf
name: tinyllama
n_ctx: 4096
n_gpu_layers: -1
port: 8000

# Generation defaults
max_tokens: 256
temperature: 0.7
top_p: 0.95
top_k: 40
```

Then run:
```bash
anyserve serve --config model.yaml
```

## KServe Protocol Details

### Input Tensors

| Name | Type | Shape | Description |
|------|------|-------|-------------|
| `prompt` | BYTES | [1] | Input prompt text |
| `max_tokens` | INT32 | [1] | Max tokens to generate (optional) |
| `temperature` | FP32 | [1] | Sampling temperature (optional) |
| `top_p` | FP32 | [1] | Top-p sampling (optional) |
| `top_k` | INT32 | [1] | Top-k sampling (optional) |

### Output Tensors (non-streaming)

| Name | Type | Shape | Description |
|------|------|-------|-------------|
| `text` | BYTES | [1] | Generated text |
| `model` | BYTES | [1] | Model name |

### Output Tensors (streaming)

| Name | Type | Shape | Description |
|------|------|-------|-------------|
| `token` | BYTES | [1] | Generated token |
| `finish_reason` | BYTES | [1] | "null", "stop", or "length" |

## Python Client Example

```python
# Using OpenAI library with openai_server
import openai

openai.api_base = "http://localhost:8080/v1"
openai.api_key = "not-needed"

response = openai.Completion.create(
    model="tinyllama",
    prompt="Once upon a time",
    max_tokens=100,
)
print(response.choices[0].text)
```

## Direct AnyServe Worker Usage

For advanced use cases, you can also use the llamacpp app directly:

```bash
# Run with anyserve run command
anyserve run anyserve.builtins.llamacpp.app:app --port 8000

# Note: You need to initialize the model first in your code
```

Or in Python:

```python
from anyserve.builtins.llamacpp import create_app

# Create and configure the app
app = create_app(
    model_path="/path/to/model.gguf",
    name="my-model",
    n_ctx=2048,
)

# Run the server
app.run(port=8000)
```

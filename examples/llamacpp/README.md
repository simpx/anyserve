# LlamaCpp Serve Example

This example shows how to serve a GGUF model using `anyserve serve`.

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

```bash
# Serve the model
anyserve serve tinyllama-1.1b-chat-v1.0.Q2_K.gguf --name tinyllama --port 8000

# Or with more options
anyserve serve tinyllama-1.1b-chat-v1.0.Q2_K.gguf \
    --name tinyllama \
    --n-ctx 2048 \
    --n-gpu-layers -1 \
    --port 8000
```

## API Endpoints

The server provides OpenAI-compatible API endpoints:

### List Models
```bash
curl http://localhost:8000/v1/models
```

### Text Completion
```bash
curl -X POST http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "prompt": "Once upon a time",
        "max_tokens": 100,
        "temperature": 0.7
    }'
```

### Streaming Completion
```bash
curl -X POST http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "prompt": "Once upon a time",
        "max_tokens": 100,
        "stream": true
    }'
```

### Simple Generate Endpoint
```bash
curl -X POST http://localhost:8000/generate \
    -H "Content-Type: application/json" \
    -d '{
        "prompt": "Hello, how are you?",
        "max_tokens": 50
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

## Python Client Example

```python
import requests

# Non-streaming
response = requests.post(
    "http://localhost:8000/v1/completions",
    json={
        "prompt": "Once upon a time",
        "max_tokens": 100,
    }
)
print(response.json()["choices"][0]["text"])

# Streaming
response = requests.post(
    "http://localhost:8000/v1/completions",
    json={
        "prompt": "Once upon a time",
        "max_tokens": 100,
        "stream": True,
    },
    stream=True,
)
for line in response.iter_lines():
    if line:
        print(line.decode())
```

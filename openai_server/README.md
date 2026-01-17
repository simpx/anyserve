# OpenAI-compatible API Server for AnyServe

This is a standalone component that provides an OpenAI-compatible REST API by converting requests to KServe gRPC protocol and forwarding them to AnyServe.

## Architecture

```
OpenAI Client (curl, Python openai lib, etc.)
        ↓ (HTTP/REST - OpenAI API)
OpenAI Server (this component)
        ↓ (gRPC - KServe v2 protocol)
AnyServe (llama.cpp worker)
```

## Installation

```bash
# Install dependencies
pip install fastapi uvicorn grpcio

# Or use pip to install from requirements
pip install -r requirements.txt
```

## Usage

### 1. Start AnyServe with a model

```bash
anyserve serve /path/to/model.gguf --port 8000
```

### 2. Start the OpenAI-compatible server

```bash
python -m openai_server --anyserve-endpoint localhost:8000 --port 8080
```

### 3. Use the OpenAI API

#### Text Completion

```bash
curl http://localhost:8080/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "prompt": "Once upon a time",
        "max_tokens": 100,
        "temperature": 0.7
    }'
```

#### Chat Completion

```bash
curl http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "max_tokens": 100
    }'
```

#### Streaming

```bash
curl http://localhost:8080/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "prompt": "Once upon a time",
        "max_tokens": 100,
        "stream": true
    }'
```

## Python Client Example

```python
import openai

# Configure to use local server
openai.api_base = "http://localhost:8080/v1"
openai.api_key = "not-needed"  # Any string works

# Text completion
response = openai.Completion.create(
    model="llamacpp",
    prompt="Once upon a time",
    max_tokens=100,
)
print(response.choices[0].text)

# Chat completion
response = openai.ChatCompletion.create(
    model="llamacpp",
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
)
print(response.choices[0].message.content)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/models` | GET | List available models |
| `/v1/models/{model_id}` | GET | Get model info |
| `/v1/completions` | POST | Text completion |
| `/v1/chat/completions` | POST | Chat completion |
| `/health` | GET | Health check |

## Protocol Conversion

The server converts OpenAI API requests to KServe v2 inference protocol:

### OpenAI → KServe Mapping

| OpenAI Field | KServe Input |
|--------------|--------------|
| `prompt` | `prompt` (BYTES) |
| `max_tokens` | `max_tokens` (INT32) |
| `temperature` | `temperature` (FP32) |
| `top_p` | `top_p` (FP32) |
| `top_k` | `top_k` (INT32) |

### KServe → OpenAI Mapping

| KServe Output | OpenAI Field |
|---------------|--------------|
| `text` (BYTES) | `choices[0].text` |
| `token` (BYTES) | Streaming chunks |
| `finish_reason` (BYTES) | `choices[0].finish_reason` |

"""
OpenAI-compatible REST API Server

This server provides OpenAI-compatible endpoints and forwards requests
to an AnyServe instance using the KServe gRPC protocol.
"""

import json
import time
import uuid
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .kserve_client import KServeClient


class CompletionRequest(BaseModel):
    """OpenAI Completion API request."""
    model: str = "default"
    prompt: str
    max_tokens: Optional[int] = 256
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.95
    top_k: Optional[int] = 40
    stop: Optional[List[str]] = None
    stream: bool = False


class ChatMessage(BaseModel):
    """Chat message."""
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI Chat Completion API request."""
    model: str = "default"
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 256
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.95
    stream: bool = False


def create_app(anyserve_endpoint: str) -> FastAPI:
    """
    Create the FastAPI application.

    Args:
        anyserve_endpoint: The AnyServe gRPC endpoint (e.g., "localhost:8000")

    Returns:
        FastAPI application instance
    """
    app = FastAPI(
        title="OpenAI-compatible API for AnyServe",
        description="Converts OpenAI API requests to KServe protocol",
        version="0.1.0",
    )

    # Create KServe client
    client = KServeClient(anyserve_endpoint)

    @app.get("/")
    def root():
        """Health check."""
        return {"status": "ok", "backend": anyserve_endpoint}

    @app.get("/v1/models")
    def list_models():
        """List available models (OpenAI-compatible)."""
        # Query AnyServe for model info
        try:
            model_info = client.get_model_info()
            model_name = model_info.get("model_name", "llamacpp")
        except Exception:
            model_name = "llamacpp"

        return {
            "object": "list",
            "data": [
                {
                    "id": model_name,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "anyserve",
                }
            ]
        }

    @app.get("/v1/models/{model_id}")
    def get_model(model_id: str):
        """Get model info (OpenAI-compatible)."""
        return {
            "id": model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "anyserve",
        }

    @app.post("/v1/completions")
    def completions(request: CompletionRequest):
        """Text completion endpoint (OpenAI-compatible)."""
        request_id = f"cmpl-{uuid.uuid4().hex[:24]}"

        if request.stream:
            return StreamingResponse(
                _stream_completions(client, request, request_id),
                media_type="text/event-stream"
            )

        # Non-streaming request
        try:
            generated_text = client.generate(
                prompt=request.prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return {
            "id": request_id,
            "object": "text_completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "text": generated_text,
                    "logprobs": None,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": -1,
                "completion_tokens": -1,
                "total_tokens": -1,
            }
        }

    @app.post("/v1/chat/completions")
    def chat_completions(request: ChatCompletionRequest):
        """Chat completion endpoint (OpenAI-compatible)."""
        request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

        # Convert chat messages to prompt
        prompt = _format_chat_prompt(request.messages)

        if request.stream:
            return StreamingResponse(
                _stream_chat_completions(client, request, prompt, request_id),
                media_type="text/event-stream"
            )

        # Non-streaming request
        try:
            generated_text = client.generate(
                prompt=prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return {
            "id": request_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": generated_text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": -1,
                "completion_tokens": -1,
                "total_tokens": -1,
            }
        }

    @app.get("/health")
    def health():
        """Health check endpoint."""
        try:
            is_ready = client.is_ready()
            return {"status": "healthy" if is_ready else "unhealthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    return app


def _format_chat_prompt(messages: List[ChatMessage]) -> str:
    """Format chat messages into a prompt string."""
    # Simple format for now - can be customized per model
    parts = []
    for msg in messages:
        if msg.role == "system":
            parts.append(f"System: {msg.content}")
        elif msg.role == "user":
            parts.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            parts.append(f"Assistant: {msg.content}")
        else:
            parts.append(f"{msg.role}: {msg.content}")

    # Add prompt for assistant response
    parts.append("Assistant:")
    return "\n\n".join(parts)


def _stream_completions(client: KServeClient, request: CompletionRequest, request_id: str):
    """Stream completion responses."""
    try:
        for token in client.generate_stream(
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
        ):
            chunk = {
                "id": request_id,
                "object": "text_completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "text": token,
                        "logprobs": None,
                        "finish_reason": None,
                    }
                ]
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        # Final chunk
        final_chunk = {
            "id": request_id,
            "object": "text_completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "text": "",
                    "logprobs": None,
                    "finish_reason": "stop",
                }
            ]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        error_chunk = {"error": {"message": str(e)}}
        yield f"data: {json.dumps(error_chunk)}\n\n"


def _stream_chat_completions(client: KServeClient, request: ChatCompletionRequest, prompt: str, request_id: str):
    """Stream chat completion responses."""
    try:
        for token in client.generate_stream(
            prompt=prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
        ):
            chunk = {
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": token},
                        "finish_reason": None,
                    }
                ]
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        # Final chunk
        final_chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        error_chunk = {"error": {"message": str(e)}}
        yield f"data: {json.dumps(error_chunk)}\n\n"

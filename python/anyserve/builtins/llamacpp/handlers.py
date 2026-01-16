"""
llama.cpp request handlers.

This module provides HTTP handlers for the llama.cpp model server.
"""

from typing import Optional, List
from pydantic import BaseModel


class CompletionRequest(BaseModel):
    """Request model for text completion."""
    prompt: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repeat_penalty: Optional[float] = None
    stop: Optional[List[str]] = None
    stream: bool = False


class CompletionResponse(BaseModel):
    """Response model for text completion."""
    id: str
    model: str
    choices: List[dict]
    usage: dict


class ModelInfo(BaseModel):
    """Model information."""
    id: str
    object: str = "model"
    owned_by: str = "anyserve"


def create_app(config, engine):
    """Create FastAPI app with completion endpoints."""
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    import json
    import time
    import uuid

    app = FastAPI(title="AnyServe LlamaCpp Server", version="0.1.0")

    @app.get("/")
    def root():
        return {"status": "ok", "model": config.name}

    @app.get("/v1/models")
    def list_models():
        """List available models (OpenAI-compatible)."""
        return {
            "object": "list",
            "data": [
                {
                    "id": config.name,
                    "object": "model",
                    "owned_by": "anyserve",
                }
            ]
        }

    @app.get("/v1/models/{model_id}")
    def get_model(model_id: str):
        """Get model info (OpenAI-compatible)."""
        if model_id != config.name:
            return {"error": f"Model {model_id} not found"}, 404
        return {
            "id": config.name,
            "object": "model",
            "owned_by": "anyserve",
        }

    @app.post("/v1/completions")
    def completions(request: CompletionRequest):
        """Text completion endpoint (OpenAI-compatible)."""
        request_id = f"cmpl-{uuid.uuid4().hex[:8]}"

        if request.stream:
            def generate_stream():
                for token in engine.generate_stream(
                    prompt=request.prompt,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    top_k=request.top_k,
                    repeat_penalty=request.repeat_penalty,
                    stop=request.stop,
                ):
                    chunk = {
                        "id": request_id,
                        "object": "text_completion",
                        "created": int(time.time()),
                        "model": config.name,
                        "choices": [
                            {
                                "index": 0,
                                "text": token,
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
                    "model": config.name,
                    "choices": [
                        {
                            "index": 0,
                            "text": "",
                            "finish_reason": "stop",
                        }
                    ]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream"
            )

        # Non-streaming response
        generated_text = engine.generate(
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            repeat_penalty=request.repeat_penalty,
            stop=request.stop,
        )

        return {
            "id": request_id,
            "object": "text_completion",
            "created": int(time.time()),
            "model": config.name,
            "choices": [
                {
                    "index": 0,
                    "text": generated_text,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": -1,  # Not calculated
                "completion_tokens": -1,
                "total_tokens": -1,
            }
        }

    @app.post("/generate")
    def generate_simple(request: CompletionRequest):
        """Simple generation endpoint."""
        if request.stream:
            def generate_stream():
                for token in engine.generate_stream(
                    prompt=request.prompt,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    top_k=request.top_k,
                    repeat_penalty=request.repeat_penalty,
                    stop=request.stop,
                ):
                    yield f"data: {json.dumps({'text': token})}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream"
            )

        generated_text = engine.generate(
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            repeat_penalty=request.repeat_penalty,
            stop=request.stop,
        )

        return {"text": generated_text, "model": config.name}

    @app.get("/health")
    def health():
        """Health check endpoint."""
        return {"status": "healthy", "model_loaded": engine._model is not None}

    return app

"""
llama.cpp built-in worker for AnyServe.

This module provides a built-in worker implementation for serving
GGUF format LLM models using llama-cpp-python with KServe protocol.

Usage:
    # Factory mode (via CLI)
    anyserve run anyserve.builtins.llamacpp:create_app --factory --port 8000

    # Via serve CLI
    anyserve serve /path/to/model.gguf --port 8000
"""

import os

from .config import LlamaCppConfig
from .engine import LlamaCppEngine
from .app import app, _set_engine


def create_app():
    """Factory 函数 - 从环境变量读取配置

    Environment variables:
        ANYSERVE_LLAMACPP_MODEL_PATH: Path to the GGUF model file (required)
        ANYSERVE_LLAMACPP_NAME: Model name for API (default: "default")
        ANYSERVE_LLAMACPP_N_CTX: Context window size (default: 2048)
        ANYSERVE_LLAMACPP_N_GPU_LAYERS: GPU layers, -1 for all (default: -1)
        ANYSERVE_LLAMACPP_N_BATCH: Batch size (default: 512)
        ANYSERVE_LLAMACPP_N_THREADS: CPU threads (optional)
        ANYSERVE_LLAMACPP_OPENAI_PORT: OpenAI server port (optional, disabled if not set)
        ANYSERVE_LLAMACPP_OPENAI_HOST: OpenAI server host (default: "0.0.0.0")
        ANYSERVE_LLAMACPP_KSERVE_ENDPOINT: KServe endpoint for OpenAI server (e.g., "localhost:8000")

    Returns:
        AnyServe app instance with registered capability handlers
    """
    model_path = os.environ.get("ANYSERVE_LLAMACPP_MODEL_PATH")
    if not model_path:
        raise ValueError("ANYSERVE_LLAMACPP_MODEL_PATH environment variable is required")

    config = LlamaCppConfig(
        model_path=model_path,
        name=os.environ.get("ANYSERVE_LLAMACPP_NAME", "default"),
        n_ctx=int(os.environ.get("ANYSERVE_LLAMACPP_N_CTX", "2048")),
        n_gpu_layers=int(os.environ.get("ANYSERVE_LLAMACPP_N_GPU_LAYERS", "-1")),
        n_batch=int(os.environ.get("ANYSERVE_LLAMACPP_N_BATCH", "512")),
        n_threads=int(os.environ.get("ANYSERVE_LLAMACPP_N_THREADS")) if os.environ.get("ANYSERVE_LLAMACPP_N_THREADS") else None,
    )

    print(f"[LlamaCpp] Loading model from {model_path}...")
    engine = LlamaCppEngine(config)
    engine.load()
    print(f"[LlamaCpp] Model loaded successfully: {config.name}")

    _set_engine(engine, config)

    # Start embedded OpenAI server if configured
    openai_port = os.environ.get("ANYSERVE_LLAMACPP_OPENAI_PORT")
    if openai_port:
        openai_host = os.environ.get("ANYSERVE_LLAMACPP_OPENAI_HOST", "0.0.0.0")
        kserve_endpoint = os.environ.get("ANYSERVE_LLAMACPP_KSERVE_ENDPOINT", "localhost:8000")

        from .openai_server import start_openai_server
        start_openai_server(
            kserve_endpoint=kserve_endpoint,
            host=openai_host,
            port=int(openai_port),
        )

    return app


__all__ = ["LlamaCppConfig", "LlamaCppEngine", "app", "create_app"]

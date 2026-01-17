"""
llama.cpp built-in worker for AnyServe.

This module provides a built-in worker implementation for serving
GGUF format LLM models using llama-cpp-python with KServe protocol.

Usage:
    # Direct usage
    anyserve run anyserve.builtins.llamacpp.app:create_app("/path/to/model.gguf") --port 8000

    # Via CLI
    anyserve serve /path/to/model.gguf --port 8000
"""

from .config import LlamaCppConfig
from .engine import LlamaCppEngine
from .app import app, create_app

__all__ = ["LlamaCppConfig", "LlamaCppEngine", "app", "create_app"]

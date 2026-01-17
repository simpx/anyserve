"""
OpenAI-compatible API for llama.cpp worker.

This module provides OpenAI-compatible REST API endpoints that translate
requests to KServe gRPC protocol for the llama.cpp backend.
"""

from .server import create_app
from .kserve_client import KServeClient

__all__ = ["create_app", "KServeClient"]

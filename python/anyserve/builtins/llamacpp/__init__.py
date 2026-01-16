"""
llama.cpp built-in worker for AnyServe.

This module provides a built-in worker implementation for serving
GGUF format LLM models using llama-cpp-python.

Usage:
    anyserve serve /models/llama-7b.gguf --name llama-7b --port 8000
"""

from .config import LlamaCppConfig
from .engine import LlamaCppEngine
from .handlers import create_app

__all__ = ["LlamaCppConfig", "LlamaCppEngine", "create_server"]


class LlamaCppServer:
    """llama.cpp built-in server."""

    def __init__(self, config: LlamaCppConfig):
        self.config = config
        self.engine = LlamaCppEngine(config)
        self.app = None

    def run(self):
        """Start the server."""
        import uvicorn

        # Load model
        print(f"Loading model from {self.config.model_path}...")
        self.engine.load()
        print("Model loaded successfully.")

        # Create FastAPI app
        self.app = create_app(self.config, self.engine)

        # Start uvicorn
        print(f"Starting server on {self.config.host}:{self.config.port}")
        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
        )


def create_server(config: LlamaCppConfig) -> LlamaCppServer:
    """Create a llama.cpp server instance."""
    return LlamaCppServer(config)

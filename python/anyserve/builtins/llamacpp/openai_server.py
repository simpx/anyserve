"""
Embedded OpenAI server launcher for llama.cpp worker.

This module provides functionality to start an embedded OpenAI-compatible
server that forwards requests to the KServe gRPC endpoint.
"""

import threading
from typing import Optional


def start_openai_server(
    kserve_endpoint: str,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> threading.Thread:
    """
    Start an embedded OpenAI-compatible server in a background thread.

    The server uses the existing openai_server module and forwards requests
    to the specified KServe gRPC endpoint.

    Args:
        kserve_endpoint: KServe gRPC endpoint (e.g., "localhost:8000")
        host: Host to bind the OpenAI server to
        port: Port to bind the OpenAI server to

    Returns:
        The background thread running the server
    """
    import uvicorn
    from .openai_compat.server import create_app

    app = create_app(kserve_endpoint)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)

    # Run in a daemon thread so it exits when the main process exits
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    print(f"[OpenAI Server] Started on http://{host}:{port}")
    print(f"[OpenAI Server] Forwarding to KServe endpoint: {kserve_endpoint}")

    return thread

#!/usr/bin/env python3
"""
AnyServe API Server - Entry Point

Usage:
    python -m anyserve.api_server --port 8080
"""

import argparse
import uvicorn

from .router import create_app
from .registry import CapabilityRegistry


def main():
    parser = argparse.ArgumentParser(
        description="AnyServe API Server - Capability-based routing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m anyserve.api_server
  python -m anyserve.api_server --port 8080
  python -m anyserve.api_server --host 0.0.0.0 --port 8080
        """
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])

    args = parser.parse_args()

    print("=" * 60)
    print("AnyServe API Server - MVP Demo")
    print("=" * 60)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print()
    print("Endpoints:")
    print(f"  POST   /register     - Register a Replica")
    print(f"  DELETE /unregister   - Unregister a Replica")
    print(f"  GET    /registry     - List all Replicas")
    print(f"  POST   /infer        - Forward inference request (protobuf)")
    print(f"  POST   /infer/json   - Forward inference request (JSON)")
    print(f"  GET    /health       - Health check")
    print()
    print("Usage:")
    print("  1. Start Replicas with --api-server http://localhost:8080")
    print("  2. Send requests with X-Capability-Type header")
    print()
    print("=" * 60)
    print()

    # Create and run the app
    app = create_app()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()

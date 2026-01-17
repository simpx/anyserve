"""
OpenAI-compatible API Server Entry Point

Usage:
    python -m openai_server --anyserve-endpoint localhost:8000 --port 8080
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(
        description="OpenAI-compatible API Server for AnyServe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Start server connected to AnyServe on localhost:8000
    python -m openai_server --anyserve-endpoint localhost:8000 --port 8080

    # With custom host
    python -m openai_server --anyserve-endpoint localhost:8000 --host 0.0.0.0 --port 8080

Then use the OpenAI API:
    curl http://localhost:8080/v1/completions \\
        -H "Content-Type: application/json" \\
        -d '{"prompt": "Hello, world!", "max_tokens": 50}'
        """
    )
    parser.add_argument(
        "--anyserve-endpoint",
        required=True,
        help="AnyServe gRPC endpoint (e.g., localhost:8000)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind to (default: 8080)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    # Create the app
    from .server import create_app
    app = create_app(args.anyserve_endpoint)

    print(f"Starting OpenAI-compatible API Server")
    print(f"  Backend: {args.anyserve_endpoint}")
    print(f"  Listening on: {args.host}:{args.port}")
    print()
    print("Endpoints:")
    print(f"  GET  http://{args.host}:{args.port}/v1/models")
    print(f"  POST http://{args.host}:{args.port}/v1/completions")
    print(f"  POST http://{args.host}:{args.port}/v1/chat/completions")
    print()

    # Run the server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()

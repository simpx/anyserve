"""
AnyServe API Server - MVP Demo

Simplified API Server for capability-based routing.

Endpoints:
- POST /register     - Register a Replica (SSE long connection, auto-cleanup on disconnect)
- GET  /route        - Query route for a capability
- GET  /registry     - List all registered Replicas

Usage:
    cd api_server && python main.py --port 8080
"""

import asyncio
import json
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from registry import CapabilityRegistry


# Create FastAPI app
app = FastAPI(
    title="AnyServe API Server",
    description="MVP capability-based routing server",
    version="0.1.0",
)

# Global registry
registry = CapabilityRegistry()


# ============================================================
# Request/Response Models
# ============================================================

class RegisterRequest(BaseModel):
    replica_id: str
    endpoint: str
    capabilities: List[Dict[str, Any]]


class RegisterResponse(BaseModel):
    status: str
    replica_id: str


class RouteResponse(BaseModel):
    endpoint: str
    replica_id: str


class ErrorResponse(BaseModel):
    error: str


class ReplicaListResponse(BaseModel):
    replicas: List[Dict[str, Any]]


# ============================================================
# Endpoints
# ============================================================

@app.post("/register")
async def register(req: RegisterRequest):
    """
    Register a Replica with SSE long connection.

    The connection stays alive after registration. When disconnected,
    the Replica is automatically unregistered.

    Example:
        POST /register
        Content-Type: application/json

        {
          "replica_id": "replica-001",
          "endpoint": "localhost:50051",
          "capabilities": [
            {"model": "qwen2"},
            {"model": "llama-70b", "type": "chat"}
          ]
        }

        Response: SSE stream
        data: {"status": "registered", "replica_id": "replica-001"}
        data: {"status": "alive"}
        data: {"status": "alive"}
        ...
    """
    # Register first
    registry.register(req.replica_id, req.endpoint, req.capabilities)
    print(f"[API Server] Registered: {req.replica_id} -> {req.endpoint}")
    print(f"[API Server]   Capabilities: {req.capabilities}")

    async def event_stream():
        try:
            # Send registration confirmation
            yield f"data: {json.dumps({'status': 'registered', 'replica_id': req.replica_id})}\n\n"

            # Keep connection alive
            while True:
                yield f"data: {json.dumps({'status': 'alive'})}\n\n"
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        finally:
            # Auto-cleanup when connection is lost
            registry.unregister(req.replica_id)
            print(f"[API Server] Connection lost, unregistered: {req.replica_id}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/route")
async def route(request: Request):
    """
    Query route for a capability.

    Query params construct the capability query.
    Returns the endpoint of a matching Replica.

    Example:
        GET /route?model=qwen2&type=chat

        Response: 200 OK
        {"endpoint": "localhost:50051", "replica_id": "replica-001"}

        Response: 404 Not Found
        {"error": "no matching replica"}
    """
    # Extract query params as capability query
    query = dict(request.query_params)

    replica = registry.lookup(query)
    if not replica:
        raise HTTPException(status_code=404, detail="no matching replica")

    return RouteResponse(endpoint=replica.endpoint, replica_id=replica.replica_id)


@app.get("/registry", response_model=ReplicaListResponse)
async def list_registry():
    """
    List all registered Replicas.

    Example:
        GET /registry

        Response:
        {
          "replicas": [
            {
              "replica_id": "replica-001",
              "endpoint": "localhost:50051",
              "capabilities": [{"model": "qwen2"}, ...]
            }
          ]
        }
    """
    replicas = registry.list_all()
    return ReplicaListResponse(
        replicas=[r.to_dict() for r in replicas]
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

# ============================================================
# Main Entry Point
# ============================================================

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="AnyServe API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)

"""
anyServe Scheduler - Simple HTTP Service for Capability-based Routing

Maintains a global ServiceRegistry (Dict: Capability -> [Endpoint])
and provides HTTP API for Rust Runtime to query routing.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List
import uvicorn

app = FastAPI(title="anyServe Scheduler")

# Global ServiceRegistry: Capability -> [Endpoint]
service_registry: Dict[str, List[str]] = {}


class RegisterRequest(BaseModel):
    node_id: str
    endpoint: str
    capabilities: List[str]


class RegisterResponse(BaseModel):
    success: bool


class LookupResponse(BaseModel):
    endpoints: List[str]


@app.post("/register", response_model=RegisterResponse)
def register_node(req: RegisterRequest):
    """Register a node with its capabilities."""
    for cap in req.capabilities:
        if cap not in service_registry:
            service_registry[cap] = []
        if req.endpoint not in service_registry[cap]:
            service_registry[cap].append(req.endpoint)
            print(f"[Scheduler] Registered {req.node_id} ({req.endpoint}) for capability: {cap}")
    return RegisterResponse(success=True)


@app.get("/lookup", response_model=LookupResponse)
def lookup_capability(cap: str):
    """Lookup endpoints that can serve a capability."""
    endpoints = service_registry.get(cap, [])
    print(f"[Scheduler] Lookup '{cap}' -> {endpoints}")
    return LookupResponse(endpoints=endpoints)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/registry")
def get_registry():
    """Debug endpoint to view the full registry."""
    return service_registry


def run(host: str = "0.0.0.0", port: int = 8000):
    """Run the scheduler server."""
    print(f"[Scheduler] Starting on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run()

"""
API Server Router - HTTP/gRPC routing based on Capability.

This module provides the FastAPI application that routes
requests to the appropriate Replica based on Capability headers.
"""

from typing import Dict, List, Any, Optional
import grpc
import httpx

from fastapi import FastAPI, Request, Response, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .registry import CapabilityRegistry, ReplicaInfo, Capability


# Pydantic models for API
class CapabilityModel(BaseModel):
    """Model for capability in API requests."""
    type: Optional[str] = None
    model: Optional[str] = None
    # Allow additional fields
    class Config:
        extra = "allow"


class RegisterRequest(BaseModel):
    """Request body for replica registration."""
    replica_id: str
    endpoint: str
    capabilities: List[Dict[str, Any]]


class RegisterResponse(BaseModel):
    """Response for replica registration."""
    success: bool
    message: str


class UnregisterRequest(BaseModel):
    """Request body for replica unregistration."""
    replica_id: str


class RegistryEntry(BaseModel):
    """Entry in the registry listing."""
    replica_id: str
    endpoint: str
    capabilities: List[Dict[str, Any]]
    registered_at: str
    last_heartbeat: str


class RegistryResponse(BaseModel):
    """Response for registry listing."""
    replicas: List[RegistryEntry]
    total: int


def create_app(registry: Optional[CapabilityRegistry] = None) -> FastAPI:
    """
    Create the FastAPI application.

    Args:
        registry: Optional CapabilityRegistry instance. If not provided,
                  a new one will be created.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="AnyServe API Server",
        description="MVP API Server for capability-based routing",
        version="0.1.0",
    )

    # Use provided registry or create new one
    app.state.registry = registry or CapabilityRegistry()

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.post("/register", response_model=RegisterResponse)
    async def register(request: RegisterRequest):
        """
        Register a Replica with its capabilities.

        Called by Replicas when they start up.
        """
        registry = app.state.registry

        try:
            success = registry.register(
                replica_id=request.replica_id,
                endpoint=request.endpoint,
                capabilities=request.capabilities,
            )

            if success:
                cap_str = ", ".join(
                    str(Capability.from_dict(c)) for c in request.capabilities
                )
                return RegisterResponse(
                    success=True,
                    message=f"Registered {request.replica_id} at {request.endpoint} with capabilities: {cap_str}"
                )
            else:
                return RegisterResponse(
                    success=False,
                    message="Registration failed"
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/unregister", response_model=RegisterResponse)
    async def unregister(request: UnregisterRequest):
        """
        Unregister a Replica.

        Called by Replicas when they shut down.
        """
        registry = app.state.registry

        success = registry.unregister(request.replica_id)

        if success:
            return RegisterResponse(
                success=True,
                message=f"Unregistered {request.replica_id}"
            )
        else:
            return RegisterResponse(
                success=False,
                message=f"Replica {request.replica_id} not found"
            )

    @app.get("/registry", response_model=RegistryResponse)
    async def list_registry():
        """
        List all registered Replicas.
        """
        registry = app.state.registry
        replicas = registry.list_all()

        entries = [
            RegistryEntry(
                replica_id=r.replica_id,
                endpoint=r.endpoint,
                capabilities=[c.to_dict() for c in r.capabilities],
                registered_at=r.registered_at.isoformat(),
                last_heartbeat=r.last_heartbeat.isoformat(),
            )
            for r in replicas
        ]

        return RegistryResponse(
            replicas=entries,
            total=len(entries)
        )

    @app.post("/infer")
    async def infer(
        request: Request,
        x_capability_type: Optional[str] = Header(None, alias="X-Capability-Type"),
        x_capability_model: Optional[str] = Header(None, alias="X-Capability-Model"),
        x_delegated_from: Optional[str] = Header(None, alias="X-Delegated-From"),
        x_delegation_depth: Optional[int] = Header(0, alias="X-Delegation-Depth"),
    ):
        """
        Forward inference request to appropriate Replica.

        The request is routed based on X-Capability-* headers.
        """
        registry = app.state.registry

        # Build capability query from headers
        capability_query = {}
        if x_capability_type:
            capability_query["type"] = x_capability_type
        if x_capability_model:
            capability_query["model"] = x_capability_model

        # Also check for additional capability headers
        for header_name, header_value in request.headers.items():
            if header_name.lower().startswith("x-capability-"):
                key = header_name[13:].lower().replace("-", "_")  # Remove "X-Capability-"
                if key not in ["type", "model"]:  # Already handled
                    capability_query[key] = header_value

        if not capability_query:
            raise HTTPException(
                status_code=400,
                detail="No capability headers provided. Use X-Capability-Type, X-Capability-Model, etc."
            )

        # Build exclude list from delegation
        exclude = []
        if x_delegated_from:
            exclude.append(x_delegated_from)

        # Lookup replica
        replica = registry.lookup(capability_query, exclude=exclude)

        if replica is None:
            # No exact match, try random replica for delegation
            if x_delegation_depth == 0:
                replica = registry.get_random_replica(exclude=exclude)
                if replica is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No Replica found for capability: {capability_query}"
                    )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"No Replica found for capability (after delegation): {capability_query}"
                )

        # Read request body
        body = await request.body()

        # Forward to Replica via gRPC
        try:
            response_data = await forward_to_replica_grpc(
                replica.endpoint,
                body,
                capability_query,
            )
            return Response(
                content=response_data,
                media_type="application/x-protobuf"
            )
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to forward to Replica {replica.replica_id}: {str(e)}"
            )

    @app.post("/infer/json")
    async def infer_json(
        request: Request,
        x_capability_type: Optional[str] = Header(None, alias="X-Capability-Type"),
        x_capability_model: Optional[str] = Header(None, alias="X-Capability-Model"),
        x_delegated_from: Optional[str] = Header(None, alias="X-Delegated-From"),
        x_delegation_depth: Optional[int] = Header(0, alias="X-Delegation-Depth"),
    ):
        """
        JSON-based inference endpoint for easier testing.

        This endpoint accepts JSON and converts to protobuf for forwarding.
        """
        registry = app.state.registry

        # Build capability query from headers
        capability_query = {}
        if x_capability_type:
            capability_query["type"] = x_capability_type
        if x_capability_model:
            capability_query["model"] = x_capability_model

        if not capability_query:
            raise HTTPException(
                status_code=400,
                detail="No capability headers provided. Use X-Capability-Type, X-Capability-Model, etc."
            )

        # Build exclude list from delegation
        exclude = []
        if x_delegated_from:
            exclude.append(x_delegated_from)

        # Lookup replica
        replica = registry.lookup(capability_query, exclude=exclude)

        if replica is None:
            if x_delegation_depth == 0:
                replica = registry.get_random_replica(exclude=exclude)
                if replica is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No Replica found for capability: {capability_query}"
                    )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"No Replica found for capability (after delegation): {capability_query}"
                )

        # Read JSON body
        try:
            json_body = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

        # Forward to Replica via gRPC (JSON version)
        try:
            response_data = await forward_to_replica_grpc_json(
                replica.endpoint,
                json_body,
                capability_query,
            )
            return JSONResponse(content=response_data)
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to forward to Replica {replica.replica_id}: {str(e)}"
            )

    return app


async def forward_to_replica_grpc(
    endpoint: str,
    request_data: bytes,
    capability_query: Dict[str, Any],
) -> bytes:
    """
    Forward a protobuf request to a Replica via gRPC.

    Args:
        endpoint: Replica gRPC endpoint (e.g., "localhost:50051")
        request_data: Serialized protobuf ModelInferRequest
        capability_query: Capability query for the request

    Returns:
        Serialized protobuf ModelInferResponse
    """
    import sys
    import os

    # Add proto path
    proto_path = os.path.join(os.path.dirname(__file__), '..', '_proto')
    if proto_path not in sys.path:
        sys.path.insert(0, proto_path)

    from anyserve._proto import grpc_predict_v2_pb2
    from anyserve._proto import grpc_predict_v2_pb2_grpc

    # Create gRPC channel
    channel = grpc.aio.insecure_channel(endpoint)
    stub = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(channel)

    try:
        # Parse request
        request = grpc_predict_v2_pb2.ModelInferRequest()
        request.ParseFromString(request_data)

        # Make gRPC call
        response = await stub.ModelInfer(request)

        # Serialize response
        return response.SerializeToString()
    finally:
        await channel.close()


async def forward_to_replica_grpc_json(
    endpoint: str,
    json_data: Dict[str, Any],
    capability_query: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Forward a JSON request to a Replica via gRPC.

    Args:
        endpoint: Replica gRPC endpoint
        json_data: JSON request data
        capability_query: Capability query for the request

    Returns:
        JSON response data
    """
    import sys
    import os

    # Add proto path
    proto_path = os.path.join(os.path.dirname(__file__), '..', '_proto')
    if proto_path not in sys.path:
        sys.path.insert(0, proto_path)

    from anyserve._proto import grpc_predict_v2_pb2
    from anyserve._proto import grpc_predict_v2_pb2_grpc

    # Create gRPC channel
    channel = grpc.aio.insecure_channel(endpoint)
    stub = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(channel)

    try:
        # Build request from JSON
        request = grpc_predict_v2_pb2.ModelInferRequest()
        request.model_name = json_data.get("model_name", capability_query.get("type", "unknown"))
        request.model_version = json_data.get("model_version", "")
        request.id = json_data.get("id", "")

        # Add inputs
        for input_data in json_data.get("inputs", []):
            input_tensor = request.inputs.add()
            input_tensor.name = input_data.get("name", "input")
            input_tensor.datatype = input_data.get("datatype", "BYTES")
            input_tensor.shape.extend(input_data.get("shape", [1]))

            # Handle different content types
            contents = input_data.get("contents", {})
            if "bytes_contents" in contents:
                for b in contents["bytes_contents"]:
                    if isinstance(b, str):
                        input_tensor.contents.bytes_contents.append(b.encode())
                    else:
                        input_tensor.contents.bytes_contents.append(b)
            if "int_contents" in contents:
                input_tensor.contents.int_contents.extend(contents["int_contents"])
            if "fp32_contents" in contents:
                input_tensor.contents.fp32_contents.extend(contents["fp32_contents"])

        # Make gRPC call
        response = await stub.ModelInfer(request)

        # Convert response to JSON
        result = {
            "model_name": response.model_name,
            "model_version": response.model_version,
            "id": response.id,
            "outputs": []
        }

        for output in response.outputs:
            output_data = {
                "name": output.name,
                "datatype": output.datatype,
                "shape": list(output.shape),
                "contents": {}
            }
            if output.contents.bytes_contents:
                output_data["contents"]["bytes_contents"] = [
                    b.decode('utf-8', errors='replace')
                    for b in output.contents.bytes_contents
                ]
            if output.contents.int_contents:
                output_data["contents"]["int_contents"] = list(output.contents.int_contents)
            if output.contents.fp32_contents:
                output_data["contents"]["fp32_contents"] = list(output.contents.fp32_contents)

            result["outputs"].append(output_data)

        return result
    finally:
        await channel.close()

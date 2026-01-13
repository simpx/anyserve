"""
KServe v2 Inference Protocol support for AnyServe.

This module provides Python wrappers for KServe's ModelInferRequest/Response
and a simple decorator-based API for defining model handlers.

Supports both:
- @app.model("name") - legacy model-based routing
- @app.capability(type="chat", model="llama-70b") - capability-based routing
"""

from typing import List, Optional, Callable, Dict, Any as PyAny, Union
from dataclasses import dataclass, field


# =============================================================================
# Python Wrappers for KServe Protocol Messages
# =============================================================================

@dataclass
class InferTensorContents:
    """Contents of an inference tensor."""
    bool_contents: List[bool] = field(default_factory=list)
    int_contents: List[int] = field(default_factory=list)
    int64_contents: List[int] = field(default_factory=list)
    uint_contents: List[int] = field(default_factory=list)
    uint64_contents: List[int] = field(default_factory=list)
    fp32_contents: List[float] = field(default_factory=list)
    fp64_contents: List[float] = field(default_factory=list)
    bytes_contents: List[bytes] = field(default_factory=list)


@dataclass
class InferInputTensor:
    """Input tensor for model inference."""
    name: str
    datatype: str
    shape: List[int]
    contents: InferTensorContents = field(default_factory=InferTensorContents)
    parameters: Dict[str, PyAny] = field(default_factory=dict)

    # Convenience properties
    @property
    def int_contents(self) -> List[int]:
        return self.contents.int_contents

    @property
    def bytes_contents(self) -> List[bytes]:
        return self.contents.bytes_contents

    @property
    def fp32_contents(self) -> List[float]:
        return self.contents.fp32_contents


@dataclass
class InferOutputTensor:
    """Output tensor from model inference."""
    name: str
    datatype: str
    shape: List[int]
    contents: InferTensorContents = field(default_factory=InferTensorContents)
    parameters: Dict[str, PyAny] = field(default_factory=dict)

    # Convenience properties
    @property
    def int_contents(self) -> List[int]:
        return self.contents.int_contents

    @property
    def bytes_contents(self) -> List[bytes]:
        return self.contents.bytes_contents

    @property
    def fp32_contents(self) -> List[float]:
        return self.contents.fp32_contents


class ModelInferRequest:
    """KServe v2 ModelInferRequest."""

    def __init__(
        self,
        model_name: str,
        id: str = "",
        model_version: str = "",
        parameters: Optional[Dict[str, PyAny]] = None,
    ):
        self.model_name = model_name
        self.model_version = model_version
        self.id = id
        self.parameters = parameters or {}
        self.inputs: List[InferInputTensor] = []
        self.outputs: List[InferOutputTensor] = []
        self.raw_input_contents: List[bytes] = []

    def add_input(
        self,
        name: str,
        datatype: str,
        shape: List[int],
        int_contents: Optional[List[int]] = None,
        bytes_contents: Optional[List[bytes]] = None,
        fp32_contents: Optional[List[float]] = None,
        parameters: Optional[Dict[str, PyAny]] = None,
    ) -> InferInputTensor:
        """Add an input tensor to the request."""
        contents = InferTensorContents()
        if int_contents is not None:
            contents.int_contents = int_contents
        if bytes_contents is not None:
            contents.bytes_contents = bytes_contents
        if fp32_contents is not None:
            contents.fp32_contents = fp32_contents

        tensor = InferInputTensor(
            name=name,
            datatype=datatype,
            shape=shape,
            contents=contents,
            parameters=parameters or {},
        )
        self.inputs.append(tensor)
        return tensor

    def get_input(self, name: str) -> Optional[InferInputTensor]:
        """Get an input tensor by name."""
        for inp in self.inputs:
            if inp.name == name:
                return inp
        return None


class ModelInferResponse:
    """KServe v2 ModelInferResponse."""

    def __init__(
        self,
        model_name: str,
        id: str = "",
        model_version: str = "",
        parameters: Optional[Dict[str, PyAny]] = None,
        outputs: Optional[List[InferOutputTensor]] = None,
        error: Optional[str] = None,
    ):
        self.model_name = model_name
        self.model_version = model_version
        self.id = id
        self.parameters = parameters or {}
        self.outputs: List[InferOutputTensor] = outputs or []
        self.raw_output_contents: List[bytes] = []
        self.error = error  # For error responses

    def add_output(
        self,
        name: str,
        datatype: str,
        shape: List[int],
        int_contents: Optional[List[int]] = None,
        bytes_contents: Optional[List[bytes]] = None,
        fp32_contents: Optional[List[float]] = None,
        parameters: Optional[Dict[str, PyAny]] = None,
    ) -> InferOutputTensor:
        """Add an output tensor to the response."""
        contents = InferTensorContents()
        if int_contents is not None:
            contents.int_contents = int_contents
        if bytes_contents is not None:
            contents.bytes_contents = bytes_contents
        if fp32_contents is not None:
            contents.fp32_contents = fp32_contents

        tensor = InferOutputTensor(
            name=name,
            datatype=datatype,
            shape=shape,
            contents=contents,
            parameters=parameters or {},
        )
        self.outputs.append(tensor)
        return tensor

    def get_output(self, name: str) -> Optional[InferOutputTensor]:
        """Get an output tensor by name."""
        for out in self.outputs:
            if out.name == name:
                return out
        return None


# =============================================================================
# Context and Capability Support
# =============================================================================

@dataclass
class Capability:
    """
    Represents a Capability with key-value attributes.

    Examples:
        Capability(type="chat", model="llama-70b")
        Capability(type="embed")
    """
    attributes: Dict[str, PyAny] = field(default_factory=dict)

    def __init__(self, **kwargs):
        self.attributes = kwargs

    def matches(self, query: Dict[str, PyAny]) -> bool:
        """Check if this capability matches a query."""
        for key, value in query.items():
            if key not in self.attributes:
                return False
            if self.attributes[key] != value:
                return False
        return True

    def to_dict(self) -> Dict[str, PyAny]:
        return self.attributes.copy()

    def get(self, key: str, default: PyAny = None) -> PyAny:
        return self.attributes.get(key, default)

    def __repr__(self):
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.attributes.items())
        return f"Capability({attrs})"


class Context:
    """
    Context object passed to capability handlers.

    Provides access to:
    - objects: ObjectStore instance for creating/reading objects
    - call: Function to call other capabilities
    - replica_id: ID of the current replica
    - capability: The capability that matched this handler
    """

    def __init__(
        self,
        objects=None,
        call_func: Optional[Callable] = None,
        replica_id: Optional[str] = None,
        capability: Optional[Capability] = None,
    ):
        self._objects = objects
        self._call_func = call_func
        self.replica_id = replica_id
        self.capability = capability

    @property
    def objects(self):
        """Access the ObjectStore for creating/reading objects."""
        if self._objects is None:
            raise RuntimeError(
                "ObjectStore not available. Make sure --object-store is configured."
            )
        return self._objects

    def call(
        self,
        capability: Dict[str, PyAny],
        inputs: Dict[str, PyAny],
        **kwargs
    ):
        """
        Call another capability (cross-Replica call).

        Args:
            capability: Capability query (e.g., {"type": "embed"})
            inputs: Input data for the call
            **kwargs: Additional options

        Returns:
            Response from the target capability handler
        """
        if self._call_func is None:
            raise RuntimeError(
                "Cross-Replica call not available. Make sure --api-server is configured."
            )
        return self._call_func(capability, inputs, **kwargs)


# =============================================================================
# Model Registry and Decorator
# =============================================================================

# Type for handler functions
HandlerFunc = Callable[[ModelInferRequest], ModelInferResponse]
CapabilityHandlerFunc = Callable[[ModelInferRequest, Context], ModelInferResponse]

# Global registry: (model_name, model_version) -> handler_function
_model_registry: Dict[tuple, HandlerFunc] = {}

# Global capability registry: Capability -> handler_function
_capability_registry: Dict[str, tuple] = {}  # capability_key -> (Capability, handler)


class AnyServe:
    """
    AnyServe application class (similar to FastAPI).

    This class provides the decorator-based API for defining model handlers.

    Usage (legacy model-based):
        app = anyserve.AnyServe()

        @app.model("my_model")
        def handler(request: ModelInferRequest) -> ModelInferResponse:
            return response

    Usage (capability-based):
        app = anyserve.AnyServe()

        @app.capability(type="chat", model="llama-70b")
        def chat_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
            # context.objects for ObjectStore access
            # context.call() for cross-Replica calls
            return response

        if __name__ == "__main__":
            app.run(host="0.0.0.0", port=8000)
    """

    def __init__(self):
        # Legacy model registry: (model_name, model_version) -> handler
        self._local_registry: Dict[tuple, HandlerFunc] = {}
        # Capability registry: List of (Capability, handler, uses_context)
        self._capability_handlers: List[tuple] = []

    def model(self, name: str, version: Optional[str] = None):
        """
        Decorator to register a model handler for KServe v2 inference.

        Args:
            name: Model name (required)
            version: Model version (optional). If None, this handler will match
                     any version or requests without a version specified.

        Usage:
            @app.model("my_model")
            def my_handler(request: ModelInferRequest) -> ModelInferResponse:
                # Process request...
                return response

            @app.model("classifier", version="v2")
            def classifier_v2(request: ModelInferRequest) -> ModelInferResponse:
                # Process versioned request...
                return response
        """
        def decorator(func: Callable[[ModelInferRequest], ModelInferResponse]):
            # Register with (name, version) as key
            key = (name, version)
            self._local_registry[key] = func
            # Also register globally for backward compatibility
            _model_registry[key] = func
            print(f"[AnyServe] Registered model handler: {name}" + (f" (version={version})" if version else ""))
            return func
        return decorator

    def capability(self, **capability_attrs):
        """
        Decorator to register a capability handler.

        This is the recommended way to define handlers in MVP.
        The handler receives both request and context.

        Args:
            **capability_attrs: Key-value pairs defining the capability
                               (e.g., type="chat", model="llama-70b")

        Usage:
            @app.capability(type="chat", model="llama-70b")
            def chat_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
                # Access ObjectStore
                data = context.objects.get(request.inputs[0].bytes_contents[0])

                # Call another capability
                result = context.call(
                    capability={"type": "embed"},
                    inputs={"data": obj_ref}
                )

                return response

            @app.capability(type="embed")
            def embed_handler(request, context):
                ...
        """
        import inspect

        cap = Capability(**capability_attrs)

        def decorator(func):
            # Check if function expects context parameter
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            uses_context = len(params) >= 2

            # Register the handler
            self._capability_handlers.append((cap, func, uses_context))

            # Also register in legacy model registry for backward compatibility
            # Use type as model_name if available
            model_name = capability_attrs.get("type", "unknown")
            model_version = capability_attrs.get("model", None)
            key = (model_name, model_version)
            self._local_registry[key] = func
            _model_registry[key] = func

            cap_str = ", ".join(f"{k}={v!r}" for k, v in capability_attrs.items())
            print(f"[AnyServe] Registered capability handler: {cap_str}")
            return func

        return decorator

    def get_capabilities(self) -> List[Dict[str, PyAny]]:
        """Get list of all registered capabilities as dicts."""
        return [cap.to_dict() for cap, _, _ in self._capability_handlers]

    def find_handler(self, capability_query: Dict[str, PyAny]) -> Optional[tuple]:
        """
        Find a handler that matches the capability query.

        Returns:
            Tuple of (handler_func, uses_context) if found, None otherwise
        """
        for cap, handler, uses_context in self._capability_handlers:
            if cap.matches(capability_query):
                return (handler, uses_context, cap)
        return None

    def run(self, host: str = "0.0.0.0", port: int = 8000, **kwargs):
        """
        Run the AnyServe server.

        For production, use the CLI instead:
            anyserve your_module:app --port 8000

        Args:
            host: Host to bind to
            port: Port to bind to
            **kwargs: Additional options (for future use)
        """
        print(f"[AnyServe] To start the server, use the CLI:")
        print(f"    anyserve <module>:app --host {host} --port {port}")
        print()
        print(f"[AnyServe] Registered {len(self._local_registry)} model(s):")
        for (name, version) in self._local_registry.keys():
            version_str = f" (version={version})" if version else ""
            print(f"  - {name}{version_str}")


def model(name: str, version: Optional[str] = None):
    """
    Global decorator to register a model handler (backward compatibility).

    For new code, prefer using app.model():
        app = anyserve.AnyServe()
        @app.model("name")
        def handler(...): ...

    Args:
        name: Model name (required)
        version: Model version (optional). If None, this handler will match
                 any version or requests without a version specified.
    """
    def decorator(func: Callable[[ModelInferRequest], ModelInferResponse]):
        # Register with (name, version) as key
        key = (name, version)
        _model_registry[key] = func
        print(f"[AnyServe] Registered model handler: {name}" + (f" (version={version})" if version else ""))
        return func
    return decorator


def infer(
    target: str | ModelInferRequest,
    request: Optional[ModelInferRequest] = None
) -> ModelInferResponse:
    """
    Execute model inference for a given request.

    This function can be used in two modes:

    1. Local inference (testing):
        response = anyserve.infer(request)

    2. Remote inference (client):
        response = anyserve.infer("localhost:8000", request)

    Args:
        target: Either a ModelInferRequest (local mode) or a server address
                string like "localhost:8000" (remote mode)
        request: ModelInferRequest (only used in remote mode)

    Returns:
        ModelInferResponse from the model handler

    Raises:
        RuntimeError: If no matching model handler is found
        ValueError: If arguments are invalid
    """
    # Determine mode
    if isinstance(target, ModelInferRequest):
        # Local mode: infer(request)
        if request is not None:
            raise ValueError("When passing ModelInferRequest directly, don't provide second argument")
        return _infer_local(target)
    elif isinstance(target, str):
        # Remote mode: infer("host:port", request)
        if request is None:
            raise ValueError("Remote mode requires both target address and request")
        return _infer_remote(target, request)
    else:
        raise ValueError(f"Invalid target type: {type(target)}")


def _infer_local(request: ModelInferRequest) -> ModelInferResponse:
    """Execute model inference locally."""
    model_name = request.model_name
    model_version = request.model_version or None

    # Try exact match first (name, version)
    key = (model_name, model_version)
    if key in _model_registry:
        handler = _model_registry[key]
        return handler(request)

    # If version was specified but no exact match, try (name, None) as fallback
    if model_version:
        key = (model_name, None)
        if key in _model_registry:
            handler = _model_registry[key]
            return handler(request)

    # No handler found
    available_models = [
        f"{name}" + (f":{ver}" if ver else "")
        for name, ver in _model_registry.keys()
    ]
    raise RuntimeError(
        f"No handler found for model '{model_name}'" +
        (f" version '{model_version}'" if model_version else "") +
        f". Available models: {available_models}"
    )


def _infer_remote(target: str, request: ModelInferRequest) -> ModelInferResponse:
    """Execute model inference via gRPC to remote server."""
    # TODO: Implement gRPC client call
    # For now, just raise NotImplementedError
    raise NotImplementedError(
        f"Remote inference to {target} not yet implemented. "
        "This requires the C++ gRPC client implementation."
    )


# =============================================================================
# Protobuf Conversion Helpers (for Worker)
# =============================================================================

def _proto_to_python_request(proto_bytes: bytes) -> ModelInferRequest:
    """Convert protobuf bytes to Python ModelInferRequest."""
    # Import protobuf generated classes
    try:
        import sys
        import os
        # Add generated protobuf directory to path
        proto_path = os.path.join(os.path.dirname(__file__), '_proto')
        if proto_path not in sys.path:
            sys.path.insert(0, proto_path)

        from grpc_predict_v2_pb2 import ModelInferRequest as ProtoRequest
    except ImportError as e:
        raise ImportError(
            f"Failed to import protobuf generated code: {e}. "
            "Please ensure protobuf files are generated."
        )

    # Parse protobuf
    proto_req = ProtoRequest()
    proto_req.ParseFromString(proto_bytes)

    # Convert to Python object
    request = ModelInferRequest(
        model_name=proto_req.model_name,
        model_version=proto_req.model_version,
        id=proto_req.id,
    )

    # Convert input tensors
    for proto_input in proto_req.inputs:
        contents = InferTensorContents()

        # Copy tensor contents
        if proto_input.contents.bool_contents:
            contents.bool_contents = list(proto_input.contents.bool_contents)
        if proto_input.contents.int_contents:
            contents.int_contents = list(proto_input.contents.int_contents)
        if proto_input.contents.int64_contents:
            contents.int64_contents = list(proto_input.contents.int64_contents)
        if proto_input.contents.uint_contents:
            contents.uint_contents = list(proto_input.contents.uint_contents)
        if proto_input.contents.uint64_contents:
            contents.uint64_contents = list(proto_input.contents.uint64_contents)
        if proto_input.contents.fp32_contents:
            contents.fp32_contents = list(proto_input.contents.fp32_contents)
        if proto_input.contents.fp64_contents:
            contents.fp64_contents = list(proto_input.contents.fp64_contents)
        if proto_input.contents.bytes_contents:
            contents.bytes_contents = list(proto_input.contents.bytes_contents)

        input_tensor = InferInputTensor(
            name=proto_input.name,
            datatype=proto_input.datatype,
            shape=list(proto_input.shape),
            contents=contents,
        )
        request.inputs.append(input_tensor)

    return request


def _python_to_proto_response(response: ModelInferResponse) -> bytes:
    """Convert Python ModelInferResponse to protobuf bytes."""
    try:
        import sys
        import os
        # Add generated protobuf directory to path
        proto_path = os.path.join(os.path.dirname(__file__), '_proto')
        if proto_path not in sys.path:
            sys.path.insert(0, proto_path)

        from grpc_predict_v2_pb2 import ModelInferResponse as ProtoResponse
        # InferOutputTensor 和 InferTensorContents 都是 ModelInferResponse 的嵌套消息类型（平级）
        ProtoOutputTensor = ProtoResponse.InferOutputTensor
        ProtoTensorContents = ProtoResponse.InferTensorContents
    except ImportError as e:
        raise ImportError(
            f"Failed to import protobuf generated code: {e}. "
            "Please ensure protobuf files are generated."
        )

    # Create protobuf response
    proto_resp = ProtoResponse()
    proto_resp.model_name = response.model_name
    proto_resp.model_version = response.model_version
    proto_resp.id = response.id

    # Check if there's an error
    if hasattr(response, 'error') and response.error:
        # For errors, we still need to return valid protobuf
        # Set model info but no outputs
        pass
    else:
        # Convert output tensors
        for output in response.outputs:
            proto_output = proto_resp.outputs.add()
            proto_output.name = output.name
            proto_output.datatype = output.datatype
            proto_output.shape.extend(output.shape)

            # Copy tensor contents
            if output.contents.bool_contents:
                proto_output.contents.bool_contents.extend(output.contents.bool_contents)
            if output.contents.int_contents:
                proto_output.contents.int_contents.extend(output.contents.int_contents)
            if output.contents.int64_contents:
                proto_output.contents.int64_contents.extend(output.contents.int64_contents)
            if output.contents.uint_contents:
                proto_output.contents.uint_contents.extend(output.contents.uint_contents)
            if output.contents.uint64_contents:
                proto_output.contents.uint64_contents.extend(output.contents.uint64_contents)
            if output.contents.fp32_contents:
                proto_output.contents.fp32_contents.extend(output.contents.fp32_contents)
            if output.contents.fp64_contents:
                proto_output.contents.fp64_contents.extend(output.contents.fp64_contents)
            if output.contents.bytes_contents:
                proto_output.contents.bytes_contents.extend(output.contents.bytes_contents)

    return proto_resp.SerializeToString()

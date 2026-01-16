"""
KServe v2 Inference Protocol support for AnyServe.

This module provides Python wrappers for KServe's ModelInferRequest/Response
and a simple decorator-based API for defining capability handlers.

Usage:
    @app.capability(type="chat", model="llama-70b")
    def chat_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
        ...
"""

from typing import List, Optional, Callable, Dict, Any as PyAny, Union, Generator
from dataclasses import dataclass, field
import queue
import threading

# =============================================================================
# Capability Definition
# =============================================================================

@dataclass
class Capability:
    """
    Represents a Capability with key-value attributes.

    Examples:
        Capability(type="chat", model="llama-70b")
        Capability(type="embed")
        Capability(type="heavy", gpus=2)
    """
    attributes: Dict[str, PyAny] = field(default_factory=dict)

    def __init__(self, **kwargs):
        self.attributes = kwargs

    def matches(self, query: Dict[str, PyAny]) -> bool:
        """
        Check if this capability matches a query.

        A capability matches if all query keys exist in the capability
        with the same values.
        """
        for key, value in query.items():
            if key not in self.attributes:
                return False
            if self.attributes[key] != value:
                return False
        return True

    def to_dict(self) -> Dict[str, PyAny]:
        return self.attributes.copy()

    def get(self, key: str, default: PyAny = None) -> PyAny:
        """Get an attribute value by key."""
        return self.attributes.get(key, default)

    @classmethod
    def from_dict(cls, data: Dict[str, PyAny]) -> "Capability":
        return cls(**data)

    def __hash__(self):
        return hash(tuple(sorted(self.attributes.items())))

    def __eq__(self, other):
        if not isinstance(other, Capability):
            return False
        return self.attributes == other.attributes

    def __repr__(self):
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.attributes.items())
        return f"Capability({attrs})"


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
# Context Support
# =============================================================================

class Context:
    """
    Context object passed to capability handlers.

    Provides access to:
    - objects: ObjectStore instance for creating/reading objects
    - call: Function to call other capabilities/services
    - replica_id: ID of the current replica
    - capability: The capability that matched this handler
    """

    def __init__(
        self,
        objects=None,
        api_server: Optional[str] = None,
        replica_id: Optional[str] = None,
        capability: Optional[Capability] = None,
    ):
        self._objects = objects
        self._api_server = api_server or "http://localhost:8080"
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
        model_name: str,
        inputs: Dict[str, PyAny],
        capability: Optional[Dict[str, PyAny]] = None,
        endpoint: Optional[str] = None,
    ) -> Dict[str, PyAny]:
        """
        Call another capability/service.

        MVP implementation: Uses Client directly, bypassing Dispatcher.
        Future: Will route through Dispatcher for full traffic proxy.

        Args:
            model_name: Name of the model to call (required)
            inputs: Input data dict. Supports two formats:
                    - Simple list → auto-infer type and shape
                    - Dict with data/shape/dtype → explicit tensor format
            capability: Optional capability query for routing (e.g., {"type": "analyze"})
            endpoint: Optional endpoint to send directly (e.g., "localhost:50052")

        Returns:
            Response dict from the target service

        Routing priority:
            1. endpoint specified → send directly to endpoint
            2. capability specified → discover via API Server
            3. model_name only → MVP not supported, raises error

        Example:
            result = context.call(
                model_name="analyze",
                inputs={"tokens": ["a,b,c"], "count": [3]},
                capability={"type": "analyze"},
            )
        """
        from anyserve.worker.client import Client

        if endpoint:
            # Direct send to specified endpoint
            client = Client(endpoint=endpoint)
        elif capability:
            # Discover via API Server
            client = Client(api_server=self._api_server, capability=capability)
        else:
            # MVP does not support model_name-only routing
            raise ValueError(
                "MVP requires either 'endpoint' or 'capability'. "
                "model_name-only routing will be supported in future."
            )

        try:
            return client.infer(model_name=model_name, inputs=inputs)
        finally:
            client.close()


# =============================================================================
# Stream Support for Streaming Inference
# =============================================================================

class Stream:
    """
    Stream object for sending streaming responses.

    Used with @app.capability(stream=True) handlers to send
    multiple responses back to the client.

    Usage:
        @app.capability(type="chat", stream=True)
        def stream_handler(request, context, stream):
            for token in generate_tokens():
                stream.send(ModelStreamInferResponse(
                    infer_response=ModelInferResponse(...)
                ))
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._closed = False
        self._error: Optional[str] = None

    def send(self, response) -> None:
        """
        Send a streaming response.

        Args:
            response: ModelStreamInferResponse (proto) or dict
        """
        if self._closed:
            raise RuntimeError("Cannot send to a closed stream")
        self._queue.put(response)

    def error(self, message: str) -> None:
        """
        Send an error response and close the stream.

        Args:
            message: Error message
        """
        self._error = message
        self._queue.put({"error_message": message})
        self.close()

    def close(self) -> None:
        """Close the stream."""
        self._closed = True
        self._queue.put(None)  # Sentinel value

    def __iter__(self):
        """Iterate over stream responses."""
        return self

    def __next__(self):
        """Get next response from the stream."""
        item = self._queue.get()
        if item is None:
            raise StopIteration
        return item

    def iter_responses(self) -> Generator:
        """Generator that yields responses until stream is closed."""
        while True:
            item = self._queue.get()
            if item is None:
                break
            yield item


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

    This class provides the decorator-based API for defining capability handlers.

    Usage:
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
        # Capability registry: List of (Capability, handler, uses_context, stream)
        self._capability_handlers: List[tuple] = []

    def capability(self, stream: bool = False, **capability_attrs):
        """
        Decorator to register a capability handler.

        This is the recommended way to define handlers in MVP.
        The handler receives both request and context.

        Args:
            stream: If True, this is a streaming handler that receives a Stream object
            **capability_attrs: Key-value pairs defining the capability
                               (e.g., type="chat", model="llama-70b")

        Usage (non-streaming):
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

        Usage (streaming):
            @app.capability(type="chat", stream=True)
            def stream_handler(request: ModelInferRequest, context: Context, stream: Stream) -> None:
                for token in generate_tokens():
                    stream.send(ModelStreamInferResponse(...))
        """
        import inspect

        cap = Capability(**capability_attrs)

        def decorator(func):
            # Check if function expects context parameter
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            uses_context = len(params) >= 2

            # Register the handler with stream flag
            self._capability_handlers.append((cap, func, uses_context, stream))

            # Also register in legacy model registry for backward compatibility
            # Use type as model_name if available
            model_name = capability_attrs.get("type", "unknown")
            model_version = capability_attrs.get("model", None)
            key = (model_name, model_version)
            self._local_registry[key] = func
            _model_registry[key] = func

            stream_str = " (streaming)" if stream else ""
            cap_str = ", ".join(f"{k}={v!r}" for k, v in capability_attrs.items())
            print(f"[AnyServe] Registered capability handler: {cap_str}{stream_str}")
            return func

        return decorator

    def get_capabilities(self) -> List[Dict[str, PyAny]]:
        """Get list of all registered capabilities as dicts."""
        return [cap.to_dict() for cap, _, _, _ in self._capability_handlers]

    def find_handler(self, capability_query: Dict[str, PyAny]) -> Optional[tuple]:
        """
        Find a non-streaming handler that matches the capability query.

        Returns:
            Tuple of (handler_func, uses_context, capability) if found, None otherwise
        """
        for cap, handler, uses_context, is_stream in self._capability_handlers:
            if not is_stream and cap.matches(capability_query):
                return (handler, uses_context, cap)
        return None

    def find_stream_handler(self, capability_query: Dict[str, PyAny]) -> Optional[tuple]:
        """
        Find a streaming handler that matches the capability query.

        Returns:
            Tuple of (handler_func, uses_context, capability) if found, None otherwise
        """
        for cap, handler, uses_context, is_stream in self._capability_handlers:
            if is_stream and cap.matches(capability_query):
                return (handler, uses_context, cap)
        return None

    def find_any_handler(self, capability_query: Dict[str, PyAny]) -> Optional[tuple]:
        """
        Find any handler (streaming or non-streaming) that matches the capability query.

        Returns:
            Tuple of (handler_func, uses_context, capability, is_stream) if found, None otherwise
        """
        for cap, handler, uses_context, is_stream in self._capability_handlers:
            if cap.matches(capability_query):
                return (handler, uses_context, cap, is_stream)
        return None

    def run(self, host: str = "0.0.0.0", port: int = 8000, workers: int = 1, **kwargs):
        """
        Run the AnyServe server in development mode.

        This starts the full server stack (Dispatcher + Worker) for local development.
        For production, use the CLI instead:
            anyserve your_module:app --port 8000

        Args:
            host: Host to bind to
            port: Port to bind to
            workers: Number of workers (default: 1)
            **kwargs: Additional options (for future use)
        """
        import sys
        import os
        import inspect

        # Find the module:app string from the call stack
        frame = inspect.currentframe()
        caller_frame = frame.f_back if frame else None
        if caller_frame:
            caller_globals = caller_frame.f_globals
            module_name = caller_globals.get('__name__', '__main__')
            # Find the app variable name
            app_var_name = None
            for name, obj in caller_globals.items():
                if obj is self:
                    app_var_name = name
                    break
            if module_name == '__main__':
                # Get the actual module name from __file__
                file_path = caller_globals.get('__file__', '')
                if file_path:
                    # Convert file path to module path
                    rel_path = os.path.relpath(file_path, os.getcwd())
                    module_name = rel_path.replace('/', '.').replace('\\', '.').replace('.py', '')
            app_string = f"{module_name}:{app_var_name or 'app'}"
        else:
            app_string = "__main__:app"

        print(f"[AnyServe] Starting server in development mode...")
        print(f"[AnyServe] Application: {app_string}")
        print(f"[AnyServe] Registered {len(self._local_registry)} model(s):")
        for (name, version) in self._local_registry.keys():
            version_str = f" (version={version})" if version else ""
            print(f"  - {name}{version_str}")
        print()

        # Import and use CLI's AnyServeServer
        from anyserve.cli import AnyServeServer
        server = AnyServeServer(
            app=app_string,
            host=host,
            port=port,
            workers=workers,
            api_server=kwargs.get('api_server'),
            object_store=kwargs.get('object_store', '/tmp/anyserve-objects'),
            replica_id=kwargs.get('replica_id'),
        )
        server.start()


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

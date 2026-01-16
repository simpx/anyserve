import grpc
import struct
from enum import Enum
from typing import List, Dict, Any, Union, Optional

import requests

try:
    from .proto import grpc_predict_v2_pb2
    from .proto import grpc_predict_v2_pb2_grpc
except ImportError:
    # Fallback import logic if package structure is different
    from anyserve_worker.proto import grpc_predict_v2_pb2
    from anyserve_worker.proto import grpc_predict_v2_pb2_grpc


class ConnectionMode(Enum):
    DIRECT = "direct"
    DISCOVERY = "discovery"


class Client:
    """
    Client for interacting with AnyServe (KServe v2) models.

    Supports two connection modes:
    - Direct mode: Connect directly to a Worker endpoint
    - Discovery mode: Discover Worker endpoint via API Server /route
    """
    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_server: Optional[str] = None,
        capability: Optional[Dict[str, Any]] = None,
        lazy_connect: bool = True,
    ):
        """
        Initialize the client.

        Args:
            endpoint: Direct Worker endpoint (e.g., "localhost:50051").
                      Mutually exclusive with api_server.
            api_server: API Server URL for endpoint discovery (e.g., "http://localhost:8080").
                        Mutually exclusive with endpoint.
            capability: Capability dict for routing query. Required when using api_server.
            lazy_connect: If True, connect on first infer() call. Default True.
        """
        # Validate parameters
        if endpoint and api_server:
            raise ValueError("Cannot specify both 'endpoint' and 'api_server'")
        if not endpoint and not api_server:
            raise ValueError("Must specify either 'endpoint' or 'api_server'")
        if api_server and not capability:
            raise ValueError("'capability' required when using 'api_server'")

        self._mode = ConnectionMode.DIRECT if endpoint else ConnectionMode.DISCOVERY
        self._api_server = api_server
        self._capability = capability or {}

        # Connection state
        self._endpoint: Optional[str] = endpoint  # Pre-set for direct mode
        self._replica_id: Optional[str] = None
        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub] = None

        if not lazy_connect:
            self._ensure_connected()

    @property
    def endpoint(self) -> Optional[str]:
        """The current Worker endpoint (discovered or direct)."""
        return self._endpoint

    @property
    def replica_id(self) -> Optional[str]:
        """The replica ID from discovery (None for direct mode)."""
        return self._replica_id

    @property
    def mode(self) -> ConnectionMode:
        """The connection mode (DIRECT or DISCOVERY)."""
        return self._mode

    def _discover_endpoint(self) -> str:
        """Call API Server /route to discover Worker endpoint."""
        url = f"{self._api_server.rstrip('/')}/route"
        response = requests.get(url, params=self._capability, timeout=5.0)
        if response.status_code == 404:
            raise RuntimeError(f"No matching replica for: {self._capability}")
        response.raise_for_status()
        data = response.json()
        self._endpoint = data["endpoint"]
        self._replica_id = data.get("replica_id")
        return self._endpoint

    def _ensure_connected(self) -> None:
        """Ensure gRPC connection is established."""
        if self._stub is not None:
            return
        if self._mode == ConnectionMode.DISCOVERY and self._endpoint is None:
            self._discover_endpoint()
        self._channel = grpc.insecure_channel(self._endpoint)
        self._stub = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(self._channel)

    def _reconnect(self) -> None:
        """Force reconnection (discovery mode will re-query)."""
        if self._channel:
            self._channel.close()
        self._channel = None
        self._stub = None
        if self._mode == ConnectionMode.DISCOVERY:
            self._endpoint = None
            self._replica_id = None
        self._ensure_connected()

    def is_alive(self) -> bool:
        """Checks if the server is live."""
        try:
            self._ensure_connected()
            resp = self._stub.ServerLive(grpc_predict_v2_pb2.ServerLiveRequest())
            return resp.live
        except grpc.RpcError:
            return False

    def is_model_ready(self, model_name: str, version: str = "") -> bool:
        """Checks if a specific model is ready."""
        try:
            self._ensure_connected()
            resp = self._stub.ModelReady(grpc_predict_v2_pb2.ModelReadyRequest(name=model_name, version=version))
            return resp.ready
        except grpc.RpcError:
            return False

    def infer(
        self,
        model_name: str,
        inputs: Dict[str, List[Any]],
        version: str = "",
        retry_on_failure: bool = True,
    ) -> Dict[str, Any]:
        """
        Performs inference on the model.

        Args:
            model_name: Name of the model to call.
            inputs: Dictionary where key is input name and value is list of data.
                    Currently supports INT32 and FP32 (float) lists.
            version: Model version.
            retry_on_failure: If True and in discovery mode, retry with re-discovered
                              endpoint on failure. Default True.

        Returns:
            Dictionary of output names to data lists.
        """
        self._ensure_connected()
        request = self._build_request(model_name, inputs, version)

        try:
            response = self._stub.ModelInfer(request)
            return self._parse_response(response)
        except grpc.RpcError as e:
            if retry_on_failure and self._mode == ConnectionMode.DISCOVERY:
                self._reconnect()
                response = self._stub.ModelInfer(request)
                return self._parse_response(response)
            raise RuntimeError(f"Inference failed: {e}")

    def _build_request(
        self,
        model_name: str,
        inputs: Dict[str, List[Any]],
        version: str,
    ) -> grpc_predict_v2_pb2.ModelInferRequest:
        """Build a ModelInferRequest from inputs."""
        request = grpc_predict_v2_pb2.ModelInferRequest(
            model_name=model_name,
            model_version=version
        )

        for name, data in inputs.items():
            infer_input = grpc_predict_v2_pb2.ModelInferRequest.InferInputTensor(
                name=name,
                shape=[len(data)]
            )

            # Simple type inference
            if len(data) > 0 and isinstance(data[0], float):
                infer_input.datatype = "FP32"
                infer_input.contents.fp32_contents.extend(data)
            elif len(data) > 0 and isinstance(data[0], int):
                infer_input.datatype = "INT32"
                infer_input.contents.int_contents.extend(data)
            elif len(data) > 0 and isinstance(data[0], bytes):
                infer_input.datatype = "BYTES"
                infer_input.contents.bytes_contents.extend(data)
            elif len(data) > 0 and isinstance(data[0], str):
                infer_input.datatype = "BYTES"
                infer_input.contents.bytes_contents.extend([s.encode('utf-8') for s in data])

            request.inputs.append(infer_input)

        return request

    def _parse_response(
        self,
        response: grpc_predict_v2_pb2.ModelInferResponse,
    ) -> Dict[str, Any]:
        """Parse a ModelInferResponse into a dict."""
        results = {}
        for output in response.outputs:
            if len(output.contents.fp32_contents) > 0:
                results[output.name] = list(output.contents.fp32_contents)
            elif len(output.contents.int_contents) > 0:
                results[output.name] = list(output.contents.int_contents)
            elif len(output.contents.bytes_contents) > 0:
                results[output.name] = list(output.contents.bytes_contents)
        return results

    def close(self) -> None:
        """Close the gRPC channel."""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None

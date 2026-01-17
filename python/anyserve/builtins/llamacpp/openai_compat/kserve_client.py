"""
KServe gRPC Client for OpenAI-compatible API.

This client communicates with AnyServe using the KServe v2 inference protocol.
"""

from typing import Optional, Iterator, Dict, Any

import grpc

from anyserve._proto import grpc_predict_v2_pb2, grpc_predict_v2_pb2_grpc


class KServeClient:
    """
    Client for communicating with AnyServe via KServe gRPC protocol.
    """

    def __init__(self, endpoint: str):
        """
        Initialize the client.

        Args:
            endpoint: AnyServe gRPC endpoint (e.g., "localhost:8000")
        """
        self.endpoint = endpoint
        self._channel = None
        self._stub = None

    def _ensure_connected(self):
        """Ensure gRPC channel is connected."""
        if self._channel is None:
            self._channel = grpc.insecure_channel(self.endpoint)
            self._stub = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(self._channel)

    def close(self):
        """Close the gRPC channel."""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None

    def is_ready(self) -> bool:
        """Check if the server is ready."""
        self._ensure_connected()
        try:
            request = grpc_predict_v2_pb2.ServerReadyRequest()
            response = self._stub.ServerReady(request, timeout=5.0)
            return response.ready
        except grpc.RpcError:
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information from AnyServe."""
        self._ensure_connected()

        # Create request for model_info capability
        request = grpc_predict_v2_pb2.ModelInferRequest()
        request.model_name = "model_info"
        request.model_version = "llamacpp"

        try:
            response = self._stub.ModelInfer(request, timeout=10.0)
            result = {}
            for output in response.outputs:
                if output.name == "model_name" and output.contents.bytes_contents:
                    result["model_name"] = output.contents.bytes_contents[0].decode("utf-8")
                elif output.name == "n_ctx" and output.contents.int_contents:
                    result["n_ctx"] = output.contents.int_contents[0]
            return result
        except grpc.RpcError:
            return {}

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> str:
        """
        Generate text (non-streaming).

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling
            top_k: Top-k sampling

        Returns:
            Generated text
        """
        self._ensure_connected()

        # Build KServe request
        request = grpc_predict_v2_pb2.ModelInferRequest()
        request.model_name = "generate"
        request.model_version = "llamacpp"

        # Add prompt input
        prompt_input = request.inputs.add()
        prompt_input.name = "prompt"
        prompt_input.datatype = "BYTES"
        prompt_input.shape.append(1)
        prompt_input.contents.bytes_contents.append(prompt.encode("utf-8"))

        # Add optional parameters
        if max_tokens is not None:
            inp = request.inputs.add()
            inp.name = "max_tokens"
            inp.datatype = "INT32"
            inp.shape.append(1)
            inp.contents.int_contents.append(max_tokens)

        if temperature is not None:
            inp = request.inputs.add()
            inp.name = "temperature"
            inp.datatype = "FP32"
            inp.shape.append(1)
            inp.contents.fp32_contents.append(temperature)

        if top_p is not None:
            inp = request.inputs.add()
            inp.name = "top_p"
            inp.datatype = "FP32"
            inp.shape.append(1)
            inp.contents.fp32_contents.append(top_p)

        if top_k is not None:
            inp = request.inputs.add()
            inp.name = "top_k"
            inp.datatype = "INT32"
            inp.shape.append(1)
            inp.contents.int_contents.append(top_k)

        # Send request
        try:
            response = self._stub.ModelInfer(request, timeout=120.0)

            # Extract text output
            for output in response.outputs:
                if output.name == "text" and output.contents.bytes_contents:
                    return output.contents.bytes_contents[0].decode("utf-8")

            return ""
        except grpc.RpcError as e:
            raise RuntimeError(f"gRPC error: {e.code()} - {e.details()}")

    def generate_stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> Iterator[str]:
        """
        Generate text (streaming).

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling
            top_k: Top-k sampling

        Yields:
            Generated tokens
        """
        self._ensure_connected()

        # Build KServe request
        request = grpc_predict_v2_pb2.ModelInferRequest()
        request.model_name = "generate_stream"
        request.model_version = "llamacpp"

        # Add prompt input
        prompt_input = request.inputs.add()
        prompt_input.name = "prompt"
        prompt_input.datatype = "BYTES"
        prompt_input.shape.append(1)
        prompt_input.contents.bytes_contents.append(prompt.encode("utf-8"))

        # Add optional parameters
        if max_tokens is not None:
            inp = request.inputs.add()
            inp.name = "max_tokens"
            inp.datatype = "INT32"
            inp.shape.append(1)
            inp.contents.int_contents.append(max_tokens)

        if temperature is not None:
            inp = request.inputs.add()
            inp.name = "temperature"
            inp.datatype = "FP32"
            inp.shape.append(1)
            inp.contents.fp32_contents.append(temperature)

        if top_p is not None:
            inp = request.inputs.add()
            inp.name = "top_p"
            inp.datatype = "FP32"
            inp.shape.append(1)
            inp.contents.fp32_contents.append(top_p)

        if top_k is not None:
            inp = request.inputs.add()
            inp.name = "top_k"
            inp.datatype = "INT32"
            inp.shape.append(1)
            inp.contents.int_contents.append(top_k)

        # Send streaming request
        try:
            for response in self._stub.ModelStreamInfer(request):
                # Check for error
                if response.error_message:
                    raise RuntimeError(f"Streaming error: {response.error_message}")

                # Extract token from response
                for output in response.infer_response.outputs:
                    if output.name == "token" and output.contents.bytes_contents:
                        token = output.contents.bytes_contents[0].decode("utf-8")
                        if token:  # Skip empty tokens
                            yield token

                    # Check finish reason
                    if output.name == "finish_reason" and output.contents.bytes_contents:
                        reason = output.contents.bytes_contents[0].decode("utf-8")
                        if reason == "stop":
                            return

        except grpc.RpcError as e:
            raise RuntimeError(f"gRPC streaming error: {e.code()} - {e.details()}")

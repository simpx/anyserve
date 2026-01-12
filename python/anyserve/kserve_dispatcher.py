"""
KServe Dispatcher - Bridge between C++ gRPC and Python model handlers.

This module provides a dispatcher that:
1. Receives protobuf ModelInferRequest from C++ (via pickle)
2. Converts it to Python ModelInferRequest objects
3. Calls the registered @app.model() handler
4. Converts Python ModelInferResponse back to protobuf
5. Returns serialized protobuf to C++
"""

import pickle
from typing import Dict, Tuple, Callable

try:
    from anyserve.kserve import (
        ModelInferRequest,
        ModelInferResponse,
        InferInputTensor,
        InferOutputTensor,
        InferTensorContents,
        _model_registry,
    )
except ImportError:
    from .kserve import (
        ModelInferRequest,
        ModelInferResponse,
        InferInputTensor,
        InferOutputTensor,
        InferTensorContents,
        _model_registry,
    )


class KServeDispatcher:
    """
    Dispatcher for KServe v2 model inference requests.

    This class acts as a bridge between C++ gRPC server and Python model handlers.
    It receives serialized protobuf ModelInferRequest, converts to Python objects,
    calls the appropriate model handler, and returns serialized protobuf response.
    """

    def dispatch(self, capability: str, request_bytes: bytes, is_delegated: bool = False) -> bytes:
        """
        Dispatch a KServe ModelInfer request to the appropriate model handler.

        Args:
            capability: Model name (from ModelInferRequest.model_name)
            request_bytes: Serialized ModelInferRequest (protobuf or pickle)
            is_delegated: Whether this request has been delegated

        Returns:
            Serialized ModelInferResponse (protobuf or pickle)

        Raises:
            RuntimeError: If model handler not found or execution fails
        """
        try:
            # Parse request
            request = self._parse_request(request_bytes)

            # Find and call model handler
            model_name = request.model_name
            model_version = request.model_version or None

            # Try exact match first (name, version)
            key = (model_name, model_version)
            if key in _model_registry:
                handler = _model_registry[key]
                response = handler(request)
            else:
                # Try fallback (name, None)
                if model_version:
                    key = (model_name, None)
                    if key in _model_registry:
                        handler = _model_registry[key]
                        response = handler(request)
                    else:
                        raise RuntimeError(f"No handler found for model '{model_name}' version '{model_version}'")
                else:
                    available = [f"{n}:{v}" if v else n for n, v in _model_registry.keys()]
                    raise RuntimeError(
                        f"No handler found for model '{model_name}'. "
                        f"Available models: {available}"
                    )

            # Serialize response
            return self._serialize_response(response)

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"KServe dispatch failed: {str(e)}")

    def _parse_request(self, request_bytes: bytes) -> ModelInferRequest:
        """
        Parse request bytes into Python ModelInferRequest.

        C++ sends protobuf-serialized ModelInferRequest, we convert to Python objects.

        Args:
            request_bytes: Serialized request (protobuf or pickle)

        Returns:
            ModelInferRequest Python object
        """
        # Try pickle first (for local testing)
        try:
            request = pickle.loads(request_bytes)
            if isinstance(request, ModelInferRequest):
                return request
        except:
            pass

        # Parse protobuf
        try:
            import sys
            import os
            proto_path = os.path.join(os.path.dirname(__file__), "_proto")
            if proto_path not in sys.path:
                sys.path.insert(0, proto_path)

            from grpc_predict_v2_pb2 import ModelInferRequest as ProtoRequest

            proto_req = ProtoRequest()
            proto_req.ParseFromString(request_bytes)

            # Convert protobuf to Python ModelInferRequest
            request = self._proto_to_python_request(proto_req)
            return request

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(
                f"Failed to parse ModelInferRequest: {str(e)}. "
                "Make sure protobuf files are compiled."
            )

    def _proto_to_python_request(self, proto_req) -> ModelInferRequest:
        """Convert protobuf ModelInferRequest to Python object."""
        request = ModelInferRequest(
            model_name=proto_req.model_name,
            model_version=proto_req.model_version,
            id=proto_req.id,
        )

        # Convert inputs
        for proto_input in proto_req.inputs:
            contents = InferTensorContents()
            if proto_input.HasField("contents"):
                c = proto_input.contents
                contents.bool_contents = list(c.bool_contents)
                contents.int_contents = list(c.int_contents)
                contents.int64_contents = list(c.int64_contents)
                contents.uint_contents = list(c.uint_contents)
                contents.uint64_contents = list(c.uint64_contents)
                contents.fp32_contents = list(c.fp32_contents)
                contents.fp64_contents = list(c.fp64_contents)
                contents.bytes_contents = list(c.bytes_contents)

            tensor = InferInputTensor(
                name=proto_input.name,
                datatype=proto_input.datatype,
                shape=list(proto_input.shape),
                contents=contents,
            )
            request.inputs.append(tensor)

        return request

    def _python_to_proto_response(self, py_resp: ModelInferResponse):
        """Convert Python ModelInferResponse to protobuf."""
        import sys
        import os
        proto_path = os.path.join(os.path.dirname(__file__), "_proto")
        if proto_path not in sys.path:
            sys.path.insert(0, proto_path)

        from grpc_predict_v2_pb2 import ModelInferResponse as ProtoResponse

        proto_resp = ProtoResponse()
        proto_resp.model_name = py_resp.model_name
        proto_resp.model_version = py_resp.model_version or ""
        proto_resp.id = py_resp.id

        # Convert outputs
        for py_output in py_resp.outputs:
            proto_output = proto_resp.outputs.add()
            proto_output.name = py_output.name
            proto_output.datatype = py_output.datatype
            proto_output.shape.extend(py_output.shape)

            # Convert contents
            c = py_output.contents
            if c.bool_contents:
                proto_output.contents.bool_contents.extend(c.bool_contents)
            if c.int_contents:
                proto_output.contents.int_contents.extend(c.int_contents)
            if c.int64_contents:
                proto_output.contents.int64_contents.extend(c.int64_contents)
            if c.uint_contents:
                proto_output.contents.uint_contents.extend(c.uint_contents)
            if c.uint64_contents:
                proto_output.contents.uint64_contents.extend(c.uint64_contents)
            if c.fp32_contents:
                proto_output.contents.fp32_contents.extend(c.fp32_contents)
            if c.fp64_contents:
                proto_output.contents.fp64_contents.extend(c.fp64_contents)
            if c.bytes_contents:
                proto_output.contents.bytes_contents.extend(c.bytes_contents)

        return proto_resp

    def _serialize_response(self, response: ModelInferResponse) -> bytes:
        """
        Serialize Python ModelInferResponse to bytes.

        Converts to protobuf and serializes.

        Args:
            response: Python ModelInferResponse object

        Returns:
            Serialized response (protobuf)
        """
        try:
            proto_resp = self._python_to_proto_response(response)
            return proto_resp.SerializeToString()
        except Exception as e:
            print(f"[KServeDispatcher] Failed to serialize response: {e}")
            # Fallback to pickle for debugging
            return pickle.dumps(response)

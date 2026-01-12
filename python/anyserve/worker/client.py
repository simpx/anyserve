import grpc
import struct
from typing import List, Dict, Any, Union

try:
    from .proto import grpc_predict_v2_pb2
    from .proto import grpc_predict_v2_pb2_grpc
except ImportError:
    # Fallback import logic if package structure is different
    from anyserve_worker.proto import grpc_predict_v2_pb2
    from anyserve_worker.proto import grpc_predict_v2_pb2_grpc

class Client:
    """
    Client for interacting with AnyServe (KServe v2) models.
    """
    def __init__(self, target: str = "localhost:8080"):
        self.channel = grpc.insecure_channel(target)
        self.stub = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(self.channel)

    def is_alive(self) -> bool:
        """Checks if the server is live."""
        try:
            resp = self.stub.ServerLive(grpc_predict_v2_pb2.ServerLiveRequest())
            return resp.live
        except grpc.RpcError:
            return False

    def is_model_ready(self, model_name: str, version: str = "") -> bool:
        """Checks if a specific model is ready."""
        try:
            resp = self.stub.ModelReady(grpc_predict_v2_pb2.ModelReadyRequest(name=model_name, version=version))
            return resp.ready
        except grpc.RpcError:
            return False

    def infer(self, model_name: str, inputs: Dict[str, List[Any]], version: str = "") -> Dict[str, Any]:
        """
        Performs inference on the model.
        
        Args:
            model_name: Name of the model to call.
            inputs: Dictionary where key is input name and value is list of data.
                    Currently supports INT32 and FP32 (float) lists.
            version: Model version.
            
        Returns:
            Dictionary of output names to data lists.
        """
        request = grpc_predict_v2_pb2.ModelInferRequest(
            model_name=model_name,
            model_version=version
        )
        
        # Build Inputs
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
            
        # Call
        try:
            response = self.stub.ModelInfer(request)
        except grpc.RpcError as e:
            raise RuntimeError(f"Inference failed: {e}")

        # Parse Outputs
        results = {}
        for output in response.outputs:
            if len(output.contents.fp32_contents) > 0:
                results[output.name] = list(output.contents.fp32_contents)
            elif len(output.contents.int_contents) > 0:
                results[output.name] = list(output.contents.int_contents)
            elif len(output.contents.bytes_contents) > 0:
                results[output.name] = list(output.contents.bytes_contents)
            # Add other types as needed
            
        return results

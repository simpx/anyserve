"""
anyServe Python Worker - KServe v2 Execution Plane
"""
import os
import sys
import time
import grpc
import logging
from concurrent import futures
import socket

# Import generated protos
# Note: We are running as a module 'anyserve_worker', so relative imports work if structure is correct.
# If run as 'python -m anyserve_worker', sys.path includes CWD.
try:
    from .proto import grpc_predict_v2_pb2
    from .proto import grpc_predict_v2_pb2_grpc
except ImportError:
    # Fallback for dev environment or direct execution
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "proto"))
    import grpc_predict_v2_pb2
    import grpc_predict_v2_pb2_grpc

class InferenceService(grpc_predict_v2_pb2_grpc.GRPCInferenceServiceServicer):
    def __init__(self):
        self.ready = False
        print("[Worker] Service initialized", file=sys.stderr)

    def ServerLive(self, request, context):
        return grpc_predict_v2_pb2.ServerLiveResponse(live=True)

    def ServerReady(self, request, context):
        return grpc_predict_v2_pb2.ServerReadyResponse(ready=True)

    def ModelReady(self, request, context):
        return grpc_predict_v2_pb2.ModelReadyResponse(ready=True)

    def ServerMetadata(self, request, context):
        return grpc_predict_v2_pb2.ServerMetadataResponse(name="anyserve-python", version="0.1.0")

    def ModelMetadata(self, request, context):
        return grpc_predict_v2_pb2.ModelMetadataResponse(
            name=request.name,
            version=request.version,
            platform="python"
        )

    def ModelInfer(self, request, context):
        # ECHO implementation for now, with mock processing
        print(f"[Worker] ModelInfer called for {request.model_name}", file=sys.stderr)
        
        # Construct response
        response = grpc_predict_v2_pb2.ModelInferResponse(
            model_name=request.model_name,
            model_version=request.model_version,
            id=request.id
        )
        
        # Just echo inputs to outputs for PoC
        for inp in request.inputs:
            out = response.outputs.add()
            out.name = inp.name
            out.datatype = inp.datatype
            out.shape.extend(inp.shape)
            # Cannot copy directly due to different classes
            # out.contents.CopyFrom(inp.contents)
            out.contents.int_contents.extend(inp.contents.int_contents)
            
            # If payload is in raw_input_contents, we should handle it (omitted for brevity)
            
        print(f"[Worker] ModelInfer finished", file=sys.stderr)
        return response

def serve():
    logging.basicConfig(level=logging.INFO)
    
    uds_path = os.environ.get("ANSERVE_WORKER_UDS")
    ready_fd_str = os.environ.get("ANSERVE_READY_FD")
    
    if not uds_path:
        print("Error: ANSERVE_WORKER_UDS not set", file=sys.stderr)
        # For testing locally without env, use default or fail
        # sys.exit(1)
        uds_path = "/tmp/anyserve_debug.sock"

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    grpc_predict_v2_pb2_grpc.add_GRPCInferenceServiceServicer_to_server(
        InferenceService(), server
    )
    
    # Bind to UDS
    address = f'unix://{uds_path}'
    if os.path.exists(uds_path):
        os.unlink(uds_path)
        
    server.add_insecure_port(address)
    print(f"[Worker] Binding to {address}", file=sys.stderr)
    
    server.start()
    
    # Signal readiness
    if ready_fd_str:
        try:
            fd = int(ready_fd_str)
            with os.fdopen(fd, 'w') as f:
                f.write("READY")
                f.flush()
            print("[Worker] Signaled READY", file=sys.stderr)
        except Exception as e:
            print(f"[Worker] Failed to signal ready: {e}", file=sys.stderr)
    
    server.wait_for_termination()

def main():
    serve()

if __name__ == "__main__":
    main()

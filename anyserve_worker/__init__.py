"""
anyServe Python Worker - KServe v2 Execution Plane
"""
import os
import sys
import time
import grpc
import logging
from concurrent import futures
from typing import Callable, Any, Dict

# Import generated protos
try:
    from .proto import grpc_predict_v2_pb2
    from .proto import grpc_predict_v2_pb2_grpc
except ImportError:
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "proto"))
    import grpc_predict_v2_pb2
    import grpc_predict_v2_pb2_grpc

# Expose proto types for user handlers
ModelInferRequest = grpc_predict_v2_pb2.ModelInferRequest
ModelInferResponse = grpc_predict_v2_pb2.ModelInferResponse

# Expose Client
from .client import Client

class Worker:
    """
    The main Application class for anyServe workers.
    
    Usage:
        app = Worker()
        
        @app.model("my_model")
        def impl(request):
            return response
            
        if __name__ == "__main__":
            app.serve()
    """
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        
    def model(self, name: str):
        """Decorator to register a model handler."""
        def decorator(func):
            print(f"[Worker] Registered handler for model '{name}'", file=sys.stderr)
            self._handlers[name] = func
            return func
        return decorator

    def get_handler(self, name: str) -> Callable:
        return self._handlers.get(name)

    def serve(self):
        """Starts the gRPC server."""
        logging.basicConfig(level=logging.INFO)
        
        uds_path = os.environ.get("ANSERVE_WORKER_UDS")
        ready_fd_str = os.environ.get("ANSERVE_READY_FD")
        
        if not uds_path:
            print("Error: ANSERVE_WORKER_UDS not set", file=sys.stderr)
            # Default for debugging
            uds_path = "/tmp/anyserve_debug.sock"

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        grpc_predict_v2_pb2_grpc.add_GRPCInferenceServiceServicer_to_server(
            InferenceService(self), server
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
        
        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            server.stop(0)


class InferenceService(grpc_predict_v2_pb2_grpc.GRPCInferenceServiceServicer):
    def __init__(self, app: Worker):
        self.app = app
        print("[Worker] Service initialized", file=sys.stderr)

    def ServerLive(self, request, context):
        return grpc_predict_v2_pb2.ServerLiveResponse(live=True)

    def ServerReady(self, request, context):
        return grpc_predict_v2_pb2.ServerReadyResponse(ready=True)

    def ModelReady(self, request, context):
        # Could check if model is registered
        is_ready = self.app.get_handler(request.name) is not None
        return grpc_predict_v2_pb2.ModelReadyResponse(ready=is_ready)

    def ServerMetadata(self, request, context):
        return grpc_predict_v2_pb2.ServerMetadataResponse(name="anyserve-python", version="0.1.0")

    def ModelMetadata(self, request, context):
        return grpc_predict_v2_pb2.ModelMetadataResponse(
            name=request.name,
            version=request.version,
            platform="python"
        )

    def ModelInfer(self, request, context):
        handler = self.app.get_handler(request.model_name)
        if not handler:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Model '{request.model_name}' not found")
            return grpc_predict_v2_pb2.ModelInferResponse()
            
        try:
            # Delegate to user handler
            return handler(request)
        except Exception as e:
            print(f"[Worker] Handler error: {e}", file=sys.stderr)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return grpc_predict_v2_pb2.ModelInferResponse()

# Default instance for backward compatibility (if used as module)
app = Worker()

@app.model("echo")
def default_echo_handler(request):
    """Default handler if none specified, used for basic testing."""
    response = grpc_predict_v2_pb2.ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id
    )
    for inp in request.inputs:
        out = response.outputs.add()
        out.name = inp.name
        out.datatype = inp.datatype
        out.shape.extend(inp.shape)
        # Deep copy all fields is tricky, just basic echo for demo
        if len(inp.contents.int_contents) > 0:
            out.contents.int_contents.extend(inp.contents.int_contents)
        if len(inp.contents.fp32_contents) > 0:
            out.contents.fp32_contents.extend(inp.contents.fp32_contents)
        if len(inp.contents.bytes_contents) > 0:
             out.contents.bytes_contents.extend(inp.contents.bytes_contents)
    return response

def main():
    # If run directly as module, start the default app
    print("[Worker] Running default app...", file=sys.stderr)
    app.serve()

if __name__ == "__main__":
    main()

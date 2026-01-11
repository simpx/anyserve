import argparse
import os
import time
import grpc
from concurrent import futures
import sys
from multiprocessing import shared_memory

# Ensure we can import generated proto
sys.path.append(os.path.join(os.path.dirname(__file__), "proto"))

try:
    import grpc_predict_v2_pb2
    import grpc_predict_v2_pb2_grpc
except ImportError:
    pass

GLOBAL_SHM = None

class InferenceService(grpc_predict_v2_pb2_grpc.GRPCInferenceServiceServicer):
    def ServerLive(self, request, context):
        return grpc_predict_v2_pb2.ServerLiveResponse(live=True)

    def ServerReady(self, request, context):
        return grpc_predict_v2_pb2.ServerReadyResponse(ready=True)

    def ModelInfer(self, request, context):
        print(f"[Python] Received Inference Request: {request.id}")
        
        for inp in request.inputs:
            data = None
            source = "Protocol Body"
            
            if "__shm_offset__" in inp.parameters:
                offset = inp.parameters["__shm_offset__"].int64_param
                length = inp.parameters["__shm_len__"].int64_param
                
                if GLOBAL_SHM:
                    # ZERO-COPY READ!
                    data = GLOBAL_SHM.buf[offset : offset+length]
                    source = f"SHM[offset={offset}, len={length}]"
                else:
                    print("Error: SHM not attached")
            else:
                pass

            if data:
                preview = bytes(data[:10])
                print(f" -> Input {inp.name}: {source} | Data Preview: {preview}...")
            else:
                print(f" -> Input {inp.name}: No Data Found")

        return grpc_predict_v2_pb2.ModelInferResponse(
            model_name=request.model_name,
            model_version=request.model_version,
            id=request.id
        )

def serve(socket_path):
    global GLOBAL_SHM
    try:
        GLOBAL_SHM = shared_memory.SharedMemory(name="/anyserve-arena-kserve")
        print(f"[Python] Attached to SHM: {GLOBAL_SHM.name} ({GLOBAL_SHM.size} bytes)")
    except FileNotFoundError:
        print("[Python] Error: Could not find Shared Memory segment. Start Rust first.")
        # Continue to serve even if SHM fails (for testing)
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    grpc_predict_v2_pb2_grpc.add_GRPCInferenceServiceServicer_to_server(InferenceService(), server)
    
    if os.path.exists(socket_path):
        os.remove(socket_path)
    
    target = f"unix://{os.path.abspath(socket_path)}"
    server.add_insecure_port(target)
    print(f"[Python] Serving gRPC on {target}")
    
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    args = parser.parse_args()
    serve(args.socket)

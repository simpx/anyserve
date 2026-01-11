import grpc
from concurrent import futures
import time
import os
import sys
import mmap
import socket
from multiprocessing import shared_memory

import grpc_predict_v2_pb2
import grpc_predict_v2_pb2_grpc

UDS_PATH = "unix:///tmp/anyserve_demo.sock"
SHM_LINK = "/tmp/anyserve_demo_shm"

class InferenceServicer(grpc_predict_v2_pb2_grpc.GRPCInferenceServiceServicer):
    def __init__(self):
        self.shm_file = SHM_LINK
        
    def ModelInfer(self, request, context):
        print(f"[Python] Received request for model: {request.model_name}")
        
        # Check first input for params
        data_bytes = None
        if request.inputs:
            inp = request.inputs[0]
            if "__shm_offset__" in inp.parameters:
                offset = inp.parameters["__shm_offset__"].int64_param
                length = inp.parameters["__shm_len__"].int64_param
                print(f"[Python] Found SHM metadata: offset={offset}, len={length}")
                
                # Zero-copy read via multiprocessing.shared_memory
                try:
                    # 1. Read the SHM name from the link file
                    with open(self.shm_file, "r") as f:
                         # The rust crate might write a null-terminated string or similar.
                         # The error shows double slash if we pass /shmem..., so strip leading /
                         shm_real_name = f.read().strip().strip('\x00')
                         if shm_real_name.startswith('/'):
                             shm_real_name = shm_real_name[1:]
                    
                    # 2. Attach to SHM
                    # Note: SharedMemory expects the name. if it starts with /, it might strip it or keep it depending on python version
                    # Rust crate internal name usually starts with /
                    shm = shared_memory.SharedMemory(name=shm_real_name)
                    
                    # 3. Read buffer
                    data_bytes = bytes(shm.buf[offset:offset+length])
                    shm.close()
                    
                    print(f"[Python] Read {len(data_bytes)} bytes from SHM: {data_bytes[:50]}...")
                except Exception as e:
                    print(f"[Python] SHM Read Error: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                 print("[Python] No SHM metadata found")

        response = grpc_predict_v2_pb2.ModelInferResponse()
        response.model_name = request.model_name
        response.id = request.id
        
        # Echo back logic
        out_tensor = response.outputs.add()
        out_tensor.name = "OUTPUT_0"
        out_tensor.datatype = "BYTES"
        out_tensor.shape.extend([1])
        
        # We put the detailed result in contents
        if data_bytes:
            content_msg = b"Processed: " + data_bytes
        else:
            content_msg = b"Error: No data found"
            
        out_tensor.contents.bytes_contents.append(content_msg)
        
        return response

def serve():
    if os.path.exists("/tmp/anyserve_demo.sock"):
        os.remove("/tmp/anyserve_demo.sock")
        
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    grpc_predict_v2_pb2_grpc.add_GRPCInferenceServiceServicer_to_server(InferenceServicer(), server)
    
    server.add_insecure_port(UDS_PATH)
    server.start()
    print(f"[Python] Worker listening on {UDS_PATH}", flush=True)

    # Signal readiness via pipe if FD provided
    ready_fd = os.getenv("ANSERVE_READY_FD")
    if ready_fd:
        try:
            fd = int(ready_fd)
            os.write(fd, b"READY")
            os.close(fd)
            print(f"[Python] Signaled readiness via FD {fd}")
        except Exception as e:
            print(f"[Python] Failed to signal readiness via FD: {e}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()

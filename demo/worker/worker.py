import grpc
from concurrent import futures
import time
import os
import sys
import mmap
import socket
from multiprocessing import shared_memory
import struct

import grpc_predict_v2_pb2
import grpc_predict_v2_pb2_grpc

UDS_PATH = "unix:///tmp/anyserve_demo.sock"
SHM_SIZE = 100 * 1024 * 1024  # 100 MB

class InferenceServicer(grpc_predict_v2_pb2_grpc.GRPCInferenceServiceServicer):
    def __init__(self):
        self.shm_h2d = None
        self.shm_d2h = None
        self.d2h_offset = 0
        
    def _init_shm_h2d(self):
        if self.shm_h2d is None:
            fd_str = os.getenv("ANSERVE_H2D_FD")
            if fd_str:
                try:
                    fd = int(fd_str)
                    self.shm_h2d = mmap.mmap(fd, SHM_SIZE)
                    print(f"[Python] Attached to H2D SHM via FD {fd}")
                except Exception as e:
                     print(f"[Python] Failed to attach H2D SHM FD {fd_str}: {e}")
            else:
                print("[Python] ANSERVE_H2D_FD not set")

    def _init_shm_d2h(self):
        if self.shm_d2h is None:
            fd_str = os.getenv("ANSERVE_D2H_FD")
            if fd_str:
                try:
                    fd = int(fd_str)
                    self.shm_d2h = mmap.mmap(fd, SHM_SIZE)
                    print(f"[Python] Attached to D2H SHM via FD {fd}")
                except Exception as e:
                     print(f"[Python] Failed to attach D2H SHM FD {fd_str}: {e}")
            else:
                print("[Python] ANSERVE_D2H_FD not set")

    def _write_d2h(self, data: bytes) -> tuple[int, int]:
        """
        Writes data to D2H SHM ring buffer.
        Returns (offset, length).
        """
        self._init_shm_d2h()
        if self.shm_d2h is None:
            print("[Python] D2H SHM not ready, skipping zero-copy write.")
            return -1, 0

        length = len(data)
        if length > SHM_SIZE:
            print("[Python] Data too large for D2H SHM")
            return -1, 0
        
        # Simple ring buffer logic
        if self.d2h_offset + length > SHM_SIZE:
            self.d2h_offset = 0
            
        start = self.d2h_offset
        self.shm_d2h[start:start+length] = data
        self.d2h_offset += length
        
        return start, length

    def ModelInfer(self, request, context):
        print(f"[Python] Received request for model: {request.model_name}")
        
        # --- H2D READ LOGIC ---
        data_bytes = None
        if request.inputs:
            inp = request.inputs[0]
            # Check for H2D metadata key
            if "__shm_h2d_offset__" in inp.parameters:
                offset = inp.parameters["__shm_h2d_offset__"].int64_param
                length = inp.parameters["__shm_h2d_len__"].int64_param
                print(f"[Python] Found H2D SHM metadata: offset={offset}, len={length}")
                
                try:
                    self._init_shm_h2d()
                    if self.shm_h2d:
                        data_bytes = self.shm_h2d[offset:offset+length]
                        print(f"[Python] Read {len(data_bytes)} bytes from H2D SHM")
                except Exception as e:
                    print(f"[Python] H2D SHM Read Error: {e}")
            else:
                 # Fallback to direct bytes if no SHM metadata
                 if inp.contents.bytes_contents:
                     data_bytes = inp.contents.bytes_contents[0]
                 print("[Python] No SHM metadata found, used standard contents")

        # --- PROCESS LOGIC (Echo) ---
        response = grpc_predict_v2_pb2.ModelInferResponse()
        response.model_name = request.model_name
        response.id = request.id
        
        out_tensor = response.outputs.add()
        out_tensor.name = "OUTPUT_0"
        out_tensor.datatype = "BYTES"
        out_tensor.shape.extend([1])
        
        if data_bytes:
            # Simulate some processing
            content_msg = b"Processed: " + data_bytes
        else:
            content_msg = b"Error: No data found"

        # --- D2H WRITE LOGIC ---
        d2h_offset, d2h_len = self._write_d2h(content_msg)
        
        if d2h_offset >= 0:
            # Success: Zero-Copy Return
            print(f"[Python] Wrote {d2h_len} bytes to D2H SHM at offset {d2h_offset}")
            
            # Inject Metadata
            out_tensor.parameters["__shm_d2h_offset__"].int64_param = d2h_offset
            out_tensor.parameters["__shm_d2h_len__"].int64_param = d2h_len
        else:
            # Fallback: Copy via UDS
            print("[Python] Fallback to UDS return")
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

    # Signal readiness
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

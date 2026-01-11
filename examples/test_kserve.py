import sys
import os
import grpc

# Add root to sys.path to find anyserve_worker
sys.path.append(os.getcwd())

from anyserve_worker.proto import grpc_predict_v2_pb2
from anyserve_worker.proto import grpc_predict_v2_pb2_grpc

def main():
    print("Connecting to localhost:9000...")
    channel = grpc.insecure_channel("localhost:9000")
    client = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(channel)
    
    try:
        resp = client.ServerLive(grpc_predict_v2_pb2.ServerLiveRequest())
        print(f"ServerLive: {resp.live}")
        
        resp = client.ServerReady(grpc_predict_v2_pb2.ServerReadyRequest())
        print(f"ServerReady: {resp.ready}")
        
        # Test Inference
        req = grpc_predict_v2_pb2.ModelInferRequest(model_name="test_model", model_version="1")
        # Add input
        inp = req.inputs.add()
        inp.name = "input0"
        inp.datatype = "INT32"
        inp.shape.extend([1, 1])
        inp.contents.int_contents.append(42)
        
        resp = client.ModelInfer(req)
        print(f"ModelInfer Result: {resp}")
        
    except grpc.RpcError as e:
        print(f"RPC Error: {e}")

if __name__ == "__main__":
    main()

import grpc
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import grpc_predict_v2_pb2
import grpc_predict_v2_pb2_grpc

def run():
    print("Client connecting to localhost:50055...")
    channel = grpc.insecure_channel('localhost:50055')
    stub = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(channel)
    
    req = grpc_predict_v2_pb2.ModelInferRequest()
    req.model_name = "test_model"
    req.id = "1"
    
    # Large input to force SHM usage
    data = b"Hello from Client via Zero-Copy Path! " * 100
    req.raw_input_contents.append(data)
    
    # Input metadata needed by Rust to inject params? 
    # Rust code: if let Some(input) = req.inputs.first_mut() { ... params.insert ... }
    # So we MUST provide at least one input meta.
    inp = req.inputs.add()
    inp.name = "INPUT_0"
    inp.datatype = "BYTES"
    inp.shape.extend([1])
    
    print(f"Sending request with {len(data)} bytes...")
    try:
        resp = stub.ModelInfer(req)
        print("Response received:")
        if resp.outputs and resp.outputs[0].contents.bytes_contents:
            print(f"Output: {resp.outputs[0].contents.bytes_contents[0][:100]}")
        else:
            print("Empty response or no content")
    except grpc.RpcError as e:
        print(f"RPC Error: {e}")

if __name__ == "__main__":
    run()

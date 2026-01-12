import grpc
import sys
import os

# Ensure we can find packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from anyserve_worker.proto import grpc_predict_v2_pb2
    from anyserve_worker.proto import grpc_predict_v2_pb2_grpc
except ImportError:
    print("Could not import protos. Make sure pyproject.toml dependencies are installed or build.rs ran.")
    sys.exit(1)

def run():
    # Rust proxy listens on 8080 by default
    channel = grpc.insecure_channel('localhost:8080')
    stub = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(channel)

    # 1. Check Server Live
    print("Checking ServerLive...")
    try:
        resp = stub.ServerLive(grpc_predict_v2_pb2.ServerLiveRequest())
        print(f"ServerLive: {resp.live}")
    except grpc.RpcError as e:
        print(f"ServerLive failed (Is the server running?): {e}")
        return

    # 2. Check Model Ready
    print("Checking ModelReady for 'math_double'...")
    resp = stub.ModelReady(grpc_predict_v2_pb2.ModelReadyRequest(name="math_double", version="1"))
    print(f"ModelReady: {resp.ready}")

    # 3. Model Infer
    print("Sending ModelInferRequest to 'math_double'...")
    
    # Create input tensor [1, 2, 3] (INT32)
    infer_input = grpc_predict_v2_pb2.ModelInferRequest.InferInputTensor(
        name="input_1",
        datatype="INT32",
        shape=[3],
    )
    infer_input.contents.int_contents.extend([10, 20, 30])

    request = grpc_predict_v2_pb2.ModelInferRequest(
        model_name="math_double",
        model_version="1",
        inputs=[infer_input]
    )

    try:
        response = stub.ModelInfer(request)
        print("Received Response!")
        for output in response.outputs:
            print(f"Output: {output.name}")
            print(f"Data: {output.contents.int_contents}")
    except grpc.RpcError as e:
        print(f"ModelInfer failed: {e}")

if __name__ == '__main__':
    run()

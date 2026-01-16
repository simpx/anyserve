#!/usr/bin/env python3
"""Test client for streaming example."""

import sys
import grpc
from anyserve.worker.proto import grpc_predict_v2_pb2
from anyserve.worker.proto import grpc_predict_v2_pb2_grpc


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "9100"
    target = f"localhost:{port}"

    print(f"=== Streaming Client Demo ===")
    print(f"Connecting to: {target}\n")

    channel = grpc.insecure_channel(target)
    stub = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(channel)

    # Build request
    request = grpc_predict_v2_pb2.ModelInferRequest(
        model_name="chat",
        id="stream-test-001",
    )
    text_input = request.inputs.add()
    text_input.name = "text"
    text_input.datatype = "BYTES"
    text_input.shape.append(1)
    text_input.contents.bytes_contents.append(b"Hi")

    print("Sending streaming request...")
    print("Tokens: ", end="", flush=True)

    try:
        for response in stub.ModelStreamInfer(request):
            if response.error_message:
                print(f"\nError: {response.error_message}")
                break

            for output in response.infer_response.outputs:
                if output.name == "text_output" and output.contents.bytes_contents:
                    token = output.contents.bytes_contents[0].decode()
                    print(token, end="", flush=True)

        print("\n\n=== Streaming completed ===")

    except grpc.RpcError as e:
        print(f"\nError: {e.code()} - {e.details()}")
        sys.exit(1)


if __name__ == "__main__":
    main()

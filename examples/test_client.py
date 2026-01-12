#!/usr/bin/env python3
"""
简单的 KServe v2 gRPC 客户端测试

测试 AnyServe 新架构的端到端流程
"""

import sys
import os

# 添加 protobuf 路径
python_path = os.path.join(os.path.dirname(__file__), '..', 'python')
sys.path.insert(0, python_path)

# 也添加 _proto 路径
proto_path = os.path.join(python_path, 'anyserve', '_proto')
if os.path.exists(proto_path) and proto_path not in sys.path:
    sys.path.insert(0, proto_path)

try:
    import grpc
    # 尝试直接导入
    try:
        import grpc_predict_v2_pb2
        import grpc_predict_v2_pb2_grpc
    except ImportError:
        # 尝试从 anyserve._proto 导入
        from anyserve._proto import grpc_predict_v2_pb2
        from anyserve._proto import grpc_predict_v2_pb2_grpc
except ImportError as e:
    print(f"Error: {e}")
    print(f"Python path: {sys.path[:3]}")
    print("Please ensure grpc and protobuf files are available")
    sys.exit(1)


def test_server_live(stub):
    """测试 ServerLive"""
    print("\n=== Testing ServerLive ===")
    request = grpc_predict_v2_pb2.ServerLiveRequest()
    try:
        response = stub.ServerLive(request, timeout=5.0)
        print(f"✓ Server is live: {response.live}")
        return True
    except grpc.RpcError as e:
        print(f"✗ Error: {e.code()} - {e.details()}")
        return False


def test_server_ready(stub):
    """测试 ServerReady"""
    print("\n=== Testing ServerReady ===")
    request = grpc_predict_v2_pb2.ServerReadyRequest()
    try:
        response = stub.ServerReady(request, timeout=5.0)
        print(f"✓ Server is ready: {response.ready}")
        return True
    except grpc.RpcError as e:
        print(f"✗ Error: {e.code()} - {e.details()}")
        return False


def test_model_ready(stub, model_name, model_version=""):
    """测试 ModelReady"""
    print(f"\n=== Testing ModelReady: {model_name}" + (f":{model_version}" if model_version else "") + " ===")
    request = grpc_predict_v2_pb2.ModelReadyRequest(
        name=model_name,
        version=model_version
    )
    try:
        response = stub.ModelReady(request, timeout=5.0)
        print(f"✓ Model '{model_name}' is ready: {response.ready}")
        return response.ready
    except grpc.RpcError as e:
        print(f"✗ Error: {e.code()} - {e.details()}")
        return False


def test_echo_model(stub):
    """测试 echo 模型"""
    print("\n=== Testing Echo Model ===")

    # 创建请求
    request = grpc_predict_v2_pb2.ModelInferRequest()
    request.model_name = "echo"
    request.model_version = ""
    request.id = "test-echo-1"

    # 添加输入 tensor
    input_tensor = request.inputs.add()
    input_tensor.name = "input"
    input_tensor.datatype = "INT32"
    input_tensor.shape.extend([3])
    input_tensor.contents.int_contents.extend([1, 2, 3])

    print(f"Sending request: model={request.model_name}, id={request.id}")
    print(f"Input: {list(input_tensor.contents.int_contents)}")

    try:
        response = stub.ModelInfer(request, timeout=5.0)
        print(f"✓ Received response: model={response.model_name}, id={response.id}")
        print(f"  Outputs: {len(response.outputs)}")

        for output in response.outputs:
            print(f"  - {output.name}: datatype={output.datatype}, shape={list(output.shape)}")
            if output.contents.int_contents:
                print(f"    values={list(output.contents.int_contents)}")

        return True
    except grpc.RpcError as e:
        print(f"✗ Error: {e.code()} - {e.details()}")
        return False


def test_add_model(stub):
    """测试 add 模型"""
    print("\n=== Testing Add Model ===")

    # 创建请求
    request = grpc_predict_v2_pb2.ModelInferRequest()
    request.model_name = "add"
    request.id = "test-add-1"

    # 添加输入 a
    input_a = request.inputs.add()
    input_a.name = "a"
    input_a.datatype = "INT32"
    input_a.shape.extend([3])
    input_a.contents.int_contents.extend([1, 2, 3])

    # 添加输入 b
    input_b = request.inputs.add()
    input_b.name = "b"
    input_b.datatype = "INT32"
    input_b.shape.extend([3])
    input_b.contents.int_contents.extend([10, 20, 30])

    print(f"Sending request: a={list(input_a.contents.int_contents)}, b={list(input_b.contents.int_contents)}")

    try:
        response = stub.ModelInfer(request, timeout=5.0)
        print(f"✓ Received response:")

        for output in response.outputs:
            if output.name == "sum":
                result = list(output.contents.int_contents)
                print(f"  sum = {result}")
                expected = [11, 22, 33]
                if result == expected:
                    print(f"  ✓ Result matches expected: {expected}")
                else:
                    print(f"  ✗ Result mismatch! Expected: {expected}")

        return True
    except grpc.RpcError as e:
        print(f"✗ Error: {e.code()} - {e.details()}")
        return False


def test_classifier_model(stub):
    """测试 classifier:v1 模型"""
    print("\n=== Testing Classifier:v1 Model ===")

    # 创建请求
    request = grpc_predict_v2_pb2.ModelInferRequest()
    request.model_name = "classifier"
    request.model_version = "v1"
    request.id = "test-classifier-1"

    # 添加输入 features
    input_tensor = request.inputs.add()
    input_tensor.name = "features"
    input_tensor.datatype = "FP32"
    input_tensor.shape.extend([4])
    input_tensor.contents.fp32_contents.extend([1.0, 2.0, 3.0, 4.0])

    print(f"Sending request: features={list(input_tensor.contents.fp32_contents)}")

    try:
        response = stub.ModelInfer(request, timeout=5.0)
        print(f"✓ Received response:")

        for output in response.outputs:
            if output.name == "class":
                predicted_class = list(output.contents.int_contents)[0]
                print(f"  predicted_class = {predicted_class}")

        return True
    except grpc.RpcError as e:
        print(f"✗ Error: {e.code()} - {e.details()}")
        return False


def test_nonexistent_model(stub):
    """测试不存在的模型（应该返回错误）"""
    print("\n=== Testing Nonexistent Model (should fail) ===")

    request = grpc_predict_v2_pb2.ModelInferRequest()
    request.model_name = "nonexistent"
    request.id = "test-error-1"

    try:
        response = stub.ModelInfer(request, timeout=5.0)
        print(f"✗ Unexpected success! Should have failed.")
        return False
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            print(f"✓ Correctly returned NOT_FOUND: {e.details()}")
            return True
        else:
            print(f"✗ Wrong error code: {e.code()} - {e.details()}")
            return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Test AnyServe gRPC server')
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=8000, help='Server port')

    args = parser.parse_args()

    server_address = f"{args.host}:{args.port}"
    print(f"Connecting to AnyServe at {server_address}")
    print("=" * 60)

    # 创建 gRPC channel
    channel = grpc.insecure_channel(server_address)
    stub = grpc_predict_v2_pb2_grpc.GRPCInferenceServiceStub(channel)

    # 运行测试
    tests = [
        ("ServerLive", lambda: test_server_live(stub)),
        ("ServerReady", lambda: test_server_ready(stub)),
        ("ModelReady (echo)", lambda: test_model_ready(stub, "echo")),
        ("ModelReady (add)", lambda: test_model_ready(stub, "add")),
        ("ModelReady (classifier:v1)", lambda: test_model_ready(stub, "classifier", "v1")),
        ("Echo Model", lambda: test_echo_model(stub)),
        ("Add Model", lambda: test_add_model(stub)),
        ("Classifier Model", lambda: test_classifier_model(stub)),
        ("Nonexistent Model", lambda: test_nonexistent_model(stub)),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n✗ Test '{test_name}' raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # 关闭连接
    channel.close()

    # 打印总结
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status:8} {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

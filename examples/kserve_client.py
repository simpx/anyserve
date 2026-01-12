"""
AnyServe KServe Client Example
===============================

Usage:
    1. Start server: python examples/kserve_server.py
    2. Run client:   python examples/kserve_client.py
"""

import anyserve
from anyserve import ModelInferRequest


def test_add():
    """Test the 'add' model."""
    print("Testing 'add' model...")
    request = ModelInferRequest(model_name="add", id="req-001")
    request.add_input("a", "INT32", [3], int_contents=[1, 2, 3])
    request.add_input("b", "INT32", [3], int_contents=[10, 20, 30])

    response = anyserve.infer("localhost:8000", request)

    print(f"  Request ID: {response.id}")
    print(f"  Result: {response.get_output('sum').int_contents}")


def test_echo():
    """Test the 'echo' model."""
    print("Testing 'echo' model...")
    request = ModelInferRequest(model_name="echo", id="req-002")
    request.add_input("text", "BYTES", [1], bytes_contents=[b"hello world"])

    response = anyserve.infer("localhost:8000", request)

    print(f"  Request ID: {response.id}")
    for out in response.outputs:
        print(f"  Output '{out.name}': {out.bytes_contents}")


def test_classifier_v1():
    """Test versioned model."""
    print("Testing 'classifier' v1...")
    request = ModelInferRequest(
        model_name="classifier",
        model_version="v1",
        id="req-003",
    )
    request.add_input("features", "FP32", [4], fp32_contents=[1.0, 2.0, 3.0, 4.0])

    response = anyserve.infer("localhost:8000", request)

    print(f"  Request ID: {response.id}")
    print(f"  Predicted class: {response.get_output('class').int_contents}")


if __name__ == "__main__":
    print("=== AnyServe KServe Client Demo ===\n")

    test_add()
    print()

    test_echo()
    print()

    test_classifier_v1()

    print("\n=== All tests completed ===")

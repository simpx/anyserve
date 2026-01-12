"""
Test local inference without gRPC (for development/testing)
"""

import sys
sys.path.insert(0, "python")

from anyserve import AnyServe, ModelInferRequest, ModelInferResponse, infer

# Create app
app = AnyServe()


@app.model("add")
def add_model(request: ModelInferRequest) -> ModelInferResponse:
    """Add two INT32 tensors."""
    print(f"[add] Processing request {request.id}")

    a = request.get_input("a")
    b = request.get_input("b")

    if a is None or b is None:
        raise ValueError("Missing required inputs 'a' and 'b'")

    result = [x + y for x, y in zip(a.int_contents, b.int_contents)]

    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )
    response.add_output(
        name="sum",
        datatype="INT32",
        shape=[len(result)],
        int_contents=result,
    )

    return response


@app.model("echo")
def echo_model(request: ModelInferRequest) -> ModelInferResponse:
    """Echo back inputs."""
    print(f"[echo] Processing request {request.id}")

    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )

    for inp in request.inputs:
        out = response.add_output(
            name=f"output_{inp.name}",
            datatype=inp.datatype,
            shape=inp.shape,
        )
        out.contents = inp.contents

    return response


if __name__ == "__main__":
    print("=== Testing Local Inference ===\n")

    # Test 1: Add model
    print("Test 1: add model")
    request = ModelInferRequest(model_name="add", id="test-001")
    request.add_input("a", "INT32", [3], int_contents=[1, 2, 3])
    request.add_input("b", "INT32", [3], int_contents=[10, 20, 30])

    response = infer(request)
    print(f"  Result: {response.get_output('sum').int_contents}")
    assert response.get_output('sum').int_contents == [11, 22, 33]
    print("  ✓ Pass\n")

    # Test 2: Echo model
    print("Test 2: echo model")
    request = ModelInferRequest(model_name="echo", id="test-002")
    request.add_input("text", "BYTES", [1], bytes_contents=[b"hello"])

    response = infer(request)
    print(f"  Result: {response.get_output('output_text').bytes_contents}")
    assert response.get_output('output_text').bytes_contents == [b"hello"]
    print("  ✓ Pass\n")

    print("=== All tests passed! ===")

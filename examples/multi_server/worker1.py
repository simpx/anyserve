"""
Worker 1 - Single Capability (multiply)

This worker provides one capability: multiply two INT32 tensors.

Usage:
    anyserve examples.multiserver.worker1:app --port 50051 --api-server http://localhost:8080
"""

import anyserve
from anyserve import ModelInferRequest, ModelInferResponse

app = anyserve.AnyServe()


@app.capability(type="multiply")
def multiply_handler(request: ModelInferRequest) -> ModelInferResponse:
    """Multiply capability - multiplies two INT32 tensors element-wise."""
    print(f"[multiply] Processing request {request.id}")

    a = request.get_input("a")
    b = request.get_input("b")

    if a is None or b is None:
        raise ValueError("Missing required inputs 'a' and 'b'")

    result = [x * y for x, y in zip(a.int_contents, b.int_contents)]

    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )
    response.add_output(
        name="product",
        datatype="INT32",
        shape=[len(result)],
        int_contents=result,
    )

    return response


if __name__ == "__main__":
    print("Starting Worker 1 (multiply capability)...")
    app.run(host="0.0.0.0", port=50051)

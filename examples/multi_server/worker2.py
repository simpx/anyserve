"""
Worker 2 - Two Capabilities (divide, power)

This worker provides two capabilities:
- divide: Divide two FP32 tensors
- power: Raise FP32 base to INT32 exponent

Usage:
    anyserve examples.multi_server.worker2:app --port 50052 --api-server http://localhost:8080
"""

import anyserve
from anyserve import ModelInferRequest, ModelInferResponse

app = anyserve.AnyServe()


@app.capability(type="divide")
def divide_handler(request: ModelInferRequest) -> ModelInferResponse:
    """Divide capability - divides two FP32 tensors element-wise."""
    print(f"[divide] Processing request {request.id}")

    a = request.get_input("a")
    b = request.get_input("b")

    if a is None or b is None:
        raise ValueError("Missing required inputs 'a' and 'b'")

    result = [x / y for x, y in zip(a.fp32_contents, b.fp32_contents)]

    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )
    response.add_output(
        name="quotient",
        datatype="FP32",
        shape=[len(result)],
        fp32_contents=result,
    )

    return response


@app.capability(type="power")
def power_handler(request: ModelInferRequest) -> ModelInferResponse:
    """Power capability - raises FP32 base to INT32 exponent."""
    print(f"[power] Processing request {request.id}")

    base = request.get_input("base")
    exp = request.get_input("exp")

    if base is None or exp is None:
        raise ValueError("Missing required inputs 'base' and 'exp'")

    result = [b ** e for b, e in zip(base.fp32_contents, exp.int_contents)]

    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )
    response.add_output(
        name="result",
        datatype="FP32",
        shape=[len(result)],
        fp32_contents=result,
    )

    return response


if __name__ == "__main__":
    print("Starting Worker 2 (divide, power capabilities)...")
    app.run(host="0.0.0.0", port=50052)

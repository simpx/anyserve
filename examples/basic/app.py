"""
AnyServe Basic Example - Server Application
============================================

This example demonstrates how to create model handlers using the KServe v2
Inference Protocol with AnyServe.

Models:
    - echo: Returns all inputs as outputs
    - add: Adds two INT32 tensors element-wise
    - classifier:v1: Versioned model example

Usage:
    Development:  python examples/basic/app.py
    Production:   python -m anyserve.cli examples.basic.app:app --port 8000 --workers 1
"""

import anyserve
from anyserve import ModelInferRequest, ModelInferResponse

# Create application instance (similar to FastAPI)
app = anyserve.AnyServe()


@app.model("echo")
def echo_model(request: ModelInferRequest) -> ModelInferResponse:
    """
    Echo model - returns all inputs as outputs.

    This demonstrates the basic structure of a KServe model handler.
    """
    print(f"[echo] Processing request {request.id}")

    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )

    # Echo back all inputs as outputs
    for inp in request.inputs:
        out = response.add_output(
            name=f"output_{inp.name}",
            datatype=inp.datatype,
            shape=inp.shape,
        )
        out.contents = inp.contents

    return response


@app.model("add")
def add_model(request: ModelInferRequest) -> ModelInferResponse:
    """
    Add model - adds two INT32 tensors element-wise.

    Expects:
        - inputs[0]: "a" - INT32 tensor
        - inputs[1]: "b" - INT32 tensor

    Returns:
        - outputs[0]: "sum" - INT32 tensor (a + b)
    """
    print(f"[add] Processing request {request.id}")

    # Extract inputs
    a = request.get_input("a")
    b = request.get_input("b")

    if a is None or b is None:
        raise ValueError("Missing required inputs 'a' and 'b'")

    # Compute sum
    result = [x + y for x, y in zip(a.int_contents, b.int_contents)]

    # Build response
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


@app.model("classifier", version="v1")
def classifier_v1(request: ModelInferRequest) -> ModelInferResponse:
    """
    Versioned model example.

    By specifying version="v1", this handler only matches requests
    where model_version == "v1".

    Expects:
        - inputs[0]: "features" - FP32 tensor

    Returns:
        - outputs[0]: "class" - INT32 scalar (predicted class)
    """
    print(f"[classifier:v1] Processing request {request.id}")

    features = request.get_input("features")
    if features is None:
        raise ValueError("Missing required input 'features'")

    # Dummy classification: just return 42
    predicted_class = 42

    response = ModelInferResponse(
        model_name=request.model_name,
        model_version="v1",
        id=request.id,
    )
    response.add_output(
        name="class",
        datatype="INT32",
        shape=[1],
        int_contents=[predicted_class],
    )

    return response


if __name__ == "__main__":
    # Development mode: run with built-in server
    print("Starting AnyServe server in development mode...")
    print("Available models:")
    print("  - echo")
    print("  - add")
    print("  - classifier:v1")
    print()

    app.run(host="0.0.0.0", port=8000)

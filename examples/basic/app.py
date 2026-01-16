"""
AnyServe Basic Example - Server Application
============================================

This example demonstrates how to create capability handlers using AnyServe.

Capabilities:
    - echo: Returns all inputs as outputs
    - add: Adds two INT32 tensors element-wise
    - classifier: Versioned capability example

Usage:
    Development:  python examples/basic/app.py
    Production:   anyserve examples.basic.app:app --port 8000 --workers 1
"""

import anyserve
from anyserve import ModelInferRequest, ModelInferResponse

app = anyserve.AnyServe()


@app.capability(type="echo")
def echo_handler(request: ModelInferRequest) -> ModelInferResponse:
    """Echo capability - returns all inputs as outputs."""
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


@app.capability(type="add")
def add_handler(request: ModelInferRequest) -> ModelInferResponse:
    """Add capability - adds two INT32 tensors element-wise."""
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


@app.capability(type="classifier", version="v1")
def classifier_v1(request: ModelInferRequest) -> ModelInferResponse:
    """Classifier capability with version."""
    print(f"[classifier:v1] Processing request {request.id}")

    features = request.get_input("features")
    if features is None:
        raise ValueError("Missing required input 'features'")

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
    print("Starting AnyServe server in development mode...")
    print("Available capabilities: echo, add, classifier:v1")
    print()
    app.run(host="0.0.0.0", port=8000)

"""
AnyServe Server Example
=======================

Usage:
    Development:  python examples/server.py
    Production:   anyserve examples.server:app
"""

import anyserve
from anyserve import ModelInferRequest, ModelInferResponse

# Create application instance (similar to FastAPI)
app = anyserve.AnyServe()


@app.model("echo")
def echo_model(request: ModelInferRequest) -> ModelInferResponse:
    """Echo back all inputs as outputs."""
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


@app.model("add")
def add_model(request: ModelInferRequest) -> ModelInferResponse:
    """Add two INT32 tensors element-wise."""
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


@app.model("classifier", version="v1")
def classifier_v1(request: ModelInferRequest) -> ModelInferResponse:
    """Versioned model example."""
    response = ModelInferResponse(
        model_name=request.model_name,
        model_version="v1",
        id=request.id,
    )
    response.add_output(
        name="class",
        datatype="INT32",
        shape=[1],
        int_contents=[42],
    )
    return response


if __name__ == "__main__":
    # Development mode: run with built-in server
    app.run(host="0.0.0.0", port=8000)

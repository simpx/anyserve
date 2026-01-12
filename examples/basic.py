"""
AnyServe Basic Usage Example
============================

This example demonstrates the simplest usage pattern of AnyServe,
using the KServe v2 Inference Protocol (gRPC Predict v2).

Core Concepts:
- `@anyserve.model(name, version=None)`: Register a model handler
- Input/Output follow KServe ModelInferRequest/ModelInferResponse format

Usage:
    python -m examples.basic
"""

import anyserve
from anyserve import ModelInferRequest, ModelInferResponse


# =============================================================================
# 1. Define Models (using @anyserve.model decorator)
# =============================================================================

@anyserve.model("echo")
def echo_model(request: ModelInferRequest) -> ModelInferResponse:
    """
    A simple echo model that returns the input as output.
    
    This demonstrates the basic request/response structure following
    the KServe v2 Inference Protocol.
    """
    print(f"[echo] model_name={request.model_name}, id={request.id}")
    
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
        # Copy contents
        out.contents = inp.contents
    
    return response


@anyserve.model("add")
def add_model(request: ModelInferRequest) -> ModelInferResponse:
    """
    A model that adds two INT32 tensors element-wise.
    
    Expects:
        - inputs[0]: "a" - INT32 tensor
        - inputs[1]: "b" - INT32 tensor
    Returns:
        - outputs[0]: "sum" - INT32 tensor (a + b)
    """
    print(f"[add] model_name={request.model_name}, id={request.id}")
    
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


@anyserve.model("classifier", version="1")
def classifier_v1(request: ModelInferRequest) -> ModelInferResponse:
    """
    A versioned model example.
    
    By specifying version="1", this handler only matches requests
    where model_version == "1" (or unspecified).
    """
    print(f"[classifier v1] Processing request {request.id}")
    
    response = ModelInferResponse(
        model_name=request.model_name,
        model_version="1",
        id=request.id,
    )
    response.add_output(
        name="class",
        datatype="INT32",
        shape=[1],
        int_contents=[42],  # Dummy classification result
    )
    
    return response


# =============================================================================
# 2. Main Entry Point
# =============================================================================

def main():
    """
    Initialize AnyServe and demonstrate basic model serving.
    """
    print("=" * 60)
    print("AnyServe Basic Example (KServe v2 Protocol)")
    print("=" * 60)
    
    # Initialize AnyServe runtime
    anyserve.init(
        root_dir="./tmp_basic",
        instance_id="basic-replica",
    )
    
    # Example 1: Echo model
    print("\n[1] Testing 'echo' model...")
    request = ModelInferRequest(
        model_name="echo",
        id="req-001",
    )
    request.add_input(
        name="text",
        datatype="BYTES",
        shape=[1],
        bytes_contents=[b"Hello, AnyServe!"],
    )
    response = anyserve.infer(request)
    print(f"    Response id: {response.id}")
    print(f"    Output: {response.outputs[0].contents.bytes_contents}\n")
    
    # Example 2: Add model
    print("[2] Testing 'add' model...")
    request = ModelInferRequest(
        model_name="add",
        id="req-002",
    )
    request.add_input(name="a", datatype="INT32", shape=[3], int_contents=[1, 2, 3])
    request.add_input(name="b", datatype="INT32", shape=[3], int_contents=[10, 20, 30])
    response = anyserve.infer(request)
    print(f"    Result: {response.outputs[0].contents.int_contents}\n")
    
    # Example 3: Versioned model
    print("[3] Testing 'classifier' model (version=1)...")
    request = ModelInferRequest(
        model_name="classifier",
        model_version="1",
        id="req-003",
    )
    response = anyserve.infer(request)
    print(f"    Class: {response.outputs[0].contents.int_contents}\n")
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

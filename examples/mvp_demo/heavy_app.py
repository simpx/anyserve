"""
MVP Demo: Heavy Processing Application

This app provides a "heavy" capability for demonstration of delegation.
"""

from anyserve import AnyServe, ModelInferRequest, ModelInferResponse, Context
import time

app = AnyServe()


@app.capability(type="heavy", gpus=2)
def heavy_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
    """
    Handle heavy processing requests.

    This handler simulates a computationally intensive task.
    """
    # Get input
    text_input = ""
    for inp in request.inputs:
        if inp.name == "data" and inp.bytes_contents:
            text_input = inp.bytes_contents[0].decode('utf-8')
            break
        elif inp.name == "data" and inp.contents.bytes_contents:
            text_input = inp.contents.bytes_contents[0].decode('utf-8')
            break

    print(f"[Heavy] Processing heavy task: {text_input[:30]}...")

    # Simulate heavy computation
    time.sleep(0.5)

    # Store result as Object
    result_data = {
        "input": text_input,
        "result": f"Heavy processing completed for: {text_input}",
        "iterations": 1000,
    }
    obj_ref = context.objects.create(result_data)

    # Create response
    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )
    response.add_output(
        name="result_ref",
        datatype="BYTES",
        shape=[1],
        bytes_contents=[str(obj_ref).encode('utf-8')],
    )
    response.add_output(
        name="status",
        datatype="BYTES",
        shape=[1],
        bytes_contents=[b"completed"],
    )

    return response


if __name__ == "__main__":
    app.run()

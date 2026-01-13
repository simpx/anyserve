"""
MVP Demo: Embedding Application

This app provides an "embed" capability that can be routed by the API Server.
"""

from anyserve import AnyServe, ModelInferRequest, ModelInferResponse, Context

app = AnyServe()


@app.capability(type="embed")
def embed_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
    """
    Handle embedding requests.

    This handler:
    1. Receives text or object reference
    2. Computes a dummy embedding
    3. Returns the embedding
    """
    # Get input
    text_input = ""
    for inp in request.inputs:
        if inp.name == "text" and inp.bytes_contents:
            text_input = inp.bytes_contents[0].decode('utf-8')
            break
        elif inp.name == "text" and inp.contents.bytes_contents:
            text_input = inp.contents.bytes_contents[0].decode('utf-8')
            break
        elif inp.name == "obj_ref" and inp.bytes_contents:
            # Read from ObjectStore
            obj_ref = inp.bytes_contents[0].decode('utf-8')
            try:
                data = context.objects.get(obj_ref)
                text_input = str(data)
            except Exception as e:
                text_input = f"Error reading object: {e}"
            break

    print(f"[Embed] Processing: {text_input[:50]}...")

    # Compute dummy embedding (just length-based for demo)
    embedding = [float(len(text_input)), float(len(text_input) % 10), 0.5]

    # Create response
    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )
    response.add_output(
        name="embedding",
        datatype="FP32",
        shape=[3],
        fp32_contents=embedding,
    )

    return response


if __name__ == "__main__":
    app.run()

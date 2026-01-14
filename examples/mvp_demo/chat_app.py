"""
MVP Demo: Chat Application

This app provides a "chat" capability that can be routed by the API Server.
"""

from anyserve import AnyServe, ModelInferRequest, ModelInferResponse, Context

app = AnyServe()


@app.capability(type="chat", model="demo")
def chat_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
    """
    Handle chat requests.

    This handler:
    1. Receives a text input
    2. Optionally creates an Object and passes it to another capability
    3. Returns a response
    """
    # Get input text
    text_input = ""
    for inp in request.inputs:
        if inp.name == "text" and inp.bytes_contents:
            text_input = inp.bytes_contents[0].decode('utf-8')
            break
        elif inp.name == "text" and inp.contents.bytes_contents:
            text_input = inp.contents.bytes_contents[0].decode('utf-8')
            break

    print(f"[Chat] Received: {text_input}")

    # Simple echo response with prefix
    response_text = f"[Chat Response] You said: {text_input}"

    # Create response
    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )
    response.add_output(
        name="response",
        datatype="BYTES",
        shape=[1],
        bytes_contents=[response_text.encode('utf-8')],
    )

    return response


@app.capability(type="chat", model="with-embedding")
def chat_with_embedding_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
    """
    Handle chat requests with embedding support.

    This handler demonstrates cross-Replica calls using context.call().
    """
    # Get input text
    text_input = ""
    for inp in request.inputs:
        if inp.name == "text" and inp.bytes_contents:
            text_input = inp.bytes_contents[0].decode('utf-8')
            break

    print(f"[Chat+Embed] Received: {text_input}")

    # Store text as Object
    obj_ref = context.objects.create({"text": text_input, "processed": True})
    print(f"[Chat+Embed] Created object: {obj_ref}")

    # Simple response (in real use, would call embed capability)
    response_text = f"[Chat+Embed Response] Processed: {text_input}"

    # Create response
    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )
    response.add_output(
        name="response",
        datatype="BYTES",
        shape=[1],
        bytes_contents=[response_text.encode('utf-8')],
    )

    return response


if __name__ == "__main__":
    app.run()

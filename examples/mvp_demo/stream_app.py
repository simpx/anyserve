#!/usr/bin/env python3
"""
Stream App - Streaming capability handler example.

This example demonstrates streaming inference using @app.capability(stream=True).
"""

import time
from anyserve import AnyServe
from anyserve._proto import grpc_predict_v2_pb2


app = AnyServe()


@app.capability(type="chat", stream=True)
def chat_stream_handler(request, context, stream):
    """
    Streaming chat handler.

    Args:
        request: ModelInferRequest (proto)
        context: Context object (objects, call, etc.)
        stream: Stream object for sending responses
    """
    print(f"[stream_app] Received streaming request: id={request.id}")

    # Extract input text
    input_text = "Hello"
    for inp in request.inputs:
        if inp.name == "text" and inp.contents.bytes_contents:
            input_text = inp.contents.bytes_contents[0].decode('utf-8')
            break

    print(f"[stream_app] Input text: {input_text}")

    # Simulate token generation
    tokens = ["Hello", " ", "world", "!", " ", "This", " ", "is", " ", "streaming", "."]

    for i, token in enumerate(tokens):
        is_last = (i == len(tokens) - 1)

        # Build streaming response
        response = grpc_predict_v2_pb2.ModelStreamInferResponse(
            error_message="",
            infer_response=grpc_predict_v2_pb2.ModelInferResponse(
                model_name="chat",
                id=request.id,
            )
        )

        # Add text_output
        text_output = response.infer_response.outputs.add()
        text_output.name = "text_output"
        text_output.datatype = "BYTES"
        text_output.shape.append(1)
        text_output.contents.bytes_contents.append(token.encode())

        # Add finish_reason
        finish_output = response.infer_response.outputs.add()
        finish_output.name = "finish_reason"
        finish_output.datatype = "BYTES"
        finish_output.shape.append(1)
        finish_output.contents.bytes_contents.append(
            b"stop" if is_last else b""
        )

        # Send response
        stream.send(response)

        # Simulate processing delay
        time.sleep(0.1)

    print(f"[stream_app] Streaming completed")


# Also provide a non-streaming handler for comparison
@app.capability(type="echo")
def echo_handler(request, context):
    """Simple echo handler (non-streaming)."""
    from anyserve.kserve import ModelInferResponse, InferOutputTensor, InferTensorContents

    input_text = "no input"
    for inp in request.inputs:
        if inp.contents.bytes_contents:
            input_text = inp.contents.bytes_contents[0].decode('utf-8')
            break

    return ModelInferResponse(
        model_name="echo",
        id=request.id,
        outputs=[
            InferOutputTensor(
                name="output",
                datatype="BYTES",
                shape=[1],
                contents=InferTensorContents(
                    bytes_contents=[f"Echo: {input_text}".encode()]
                ),
            )
        ],
    )


if __name__ == "__main__":
    print("Stream App loaded with capabilities:")
    for cap in app.get_capabilities():
        print(f"  - {cap}")

import time
import anyserve
from anyserve._proto import grpc_predict_v2_pb2

app = anyserve.AnyServe()


@app.capability(type="chat", stream=True)
def chat_stream(request, context, stream):
    """Streaming chat - simulates LLM token generation."""
    print(f"[chat] Streaming request received")

    tokens = ["Hello", " ", "world", "!"]

    for i, token in enumerate(tokens):
        is_last = (i == len(tokens) - 1)

        response = grpc_predict_v2_pb2.ModelStreamInferResponse(
            infer_response=grpc_predict_v2_pb2.ModelInferResponse(
                model_name="chat",
                id=request.id,
            )
        )

        # text_output
        text_out = response.infer_response.outputs.add()
        text_out.name = "text_output"
        text_out.datatype = "BYTES"
        text_out.shape.append(1)
        text_out.contents.bytes_contents.append(token.encode())

        # finish_reason
        finish_out = response.infer_response.outputs.add()
        finish_out.name = "finish_reason"
        finish_out.datatype = "BYTES"
        finish_out.shape.append(1)
        finish_out.contents.bytes_contents.append(b"stop" if is_last else b"")

        stream.send(response)
        time.sleep(0.1)

    print(f"[chat] Streaming completed")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

"""
Worker A - Tokenize Stage

This is the first stage in the pipeline. It:
1. Receives text input (BYTES)
2. Tokenizes the text into words
3. Calls Worker B (analyze) via context.call()
4. Returns the final result

Port: 50051
Capability: type="tokenize"

Usage:
    anyserve examples.pipeline.worker_a:app --port 50051 --api-server http://localhost:8080
"""

import anyserve
from anyserve import ModelInferRequest, ModelInferResponse, Context

app = anyserve.AnyServe()


def tokenize(text: str) -> list:
    """Simple tokenizer - splits text into words."""
    # Remove punctuation and split
    import re
    words = re.findall(r'\b\w+\b', text.lower())
    return words


@app.capability(type="tokenize")
def tokenize_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
    """
    Tokenize capability - tokenizes text and calls analyze stage.

    Input:
        - text: BYTES (the text to tokenize)

    Output:
        - result: BYTES (final formatted report from the pipeline)
    """
    print(f"[tokenize] Processing request {request.id}")

    # 1. Get input text
    text_input = request.get_input("text")
    if text_input is None:
        raise ValueError("Missing required input 'text'")

    text = text_input.bytes_contents[0].decode('utf-8')
    print(f"[tokenize] Input text: {text[:100]}...")

    # 2. Tokenize the text
    tokens = tokenize(text)
    print(f"[tokenize] Found {len(tokens)} tokens")

    # 3. Call analyze stage via context.call()
    print(f"[tokenize] Calling analyze stage...")
    analyze_result = context.call(
        model_name="analyze",
        capability={"type": "analyze"},
        inputs={
            "tokens": [",".join(tokens)],  # BYTES: comma-separated tokens
            "original_text": [text],       # BYTES: original text for reference
            "token_count": [len(tokens)],  # INT32: number of tokens
        }
    )
    print(f"[tokenize] Analyze result: {analyze_result}")

    # 4. Build response with the final result
    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )

    # Pass through the final report from the pipeline
    if "report" in analyze_result:
        report_data = analyze_result["report"]
        if isinstance(report_data, list) and len(report_data) > 0:
            report_bytes = report_data[0] if isinstance(report_data[0], bytes) else report_data[0].encode('utf-8')
            response.add_output(
                name="result",
                datatype="BYTES",
                shape=[1],
                bytes_contents=[report_bytes],
            )

    return response


if __name__ == "__main__":
    print("Starting Worker A (tokenize capability)...")
    app.run(host="0.0.0.0", port=50051)

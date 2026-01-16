"""
Worker B - Analyze Stage

This is the second stage in the pipeline. It:
1. Receives tokens (BYTES) and token count (INT32)
2. Performs statistical analysis on the tokens
3. Calls Worker C (format) via context.call()
4. Returns the formatted report

Port: 50052
Capability: type="analyze"

Usage:
    anyserve examples.pipeline.worker_b:app \\
        --port 50052 --api-server http://localhost:8080
"""

import json
from collections import Counter

import anyserve
from anyserve import ModelInferRequest, ModelInferResponse, Context

app = anyserve.AnyServe()


def analyze_tokens(tokens: list) -> dict:
    """Analyze tokens and return statistics."""
    if not tokens:
        return {
            "total_tokens": 0,
            "unique_tokens": 0,
            "avg_token_length": 0.0,
            "top_tokens": [],
        }

    # Count frequencies
    freq = Counter(tokens)
    top_5 = freq.most_common(5)

    # Calculate statistics
    total = len(tokens)
    unique = len(freq)
    avg_length = sum(len(t) for t in tokens) / total if total > 0 else 0.0

    return {
        "total_tokens": total,
        "unique_tokens": unique,
        "avg_token_length": round(avg_length, 2),
        "top_tokens": [{"token": t, "count": c} for t, c in top_5],
    }


@app.capability(type="analyze")
def analyze_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
    """
    Analyze capability - analyzes tokens and calls format stage.

    Input:
        - tokens: BYTES (comma-separated token string)
        - original_text: BYTES (original text for reference)
        - token_count: INT32 (number of tokens)

    Output:
        - report: BYTES (final formatted report from format stage)
    """
    print(f"[analyze] Processing request {request.id}")

    # 1. Get inputs
    tokens_input = request.get_input("tokens")
    original_text_input = request.get_input("original_text")
    token_count_input = request.get_input("token_count")

    if tokens_input is None:
        raise ValueError("Missing required input 'tokens'")

    # Parse tokens from comma-separated string
    tokens_str = tokens_input.bytes_contents[0].decode('utf-8')
    tokens = tokens_str.split(",") if tokens_str else []

    original_text = ""
    if original_text_input and original_text_input.bytes_contents:
        original_text = original_text_input.bytes_contents[0].decode('utf-8')

    token_count = 0
    if token_count_input and token_count_input.int_contents:
        token_count = token_count_input.int_contents[0]

    print(f"[analyze] Received {len(tokens)} tokens, count={token_count}")

    # 2. Perform analysis
    stats = analyze_tokens(tokens)
    print(f"[analyze] Analysis stats: {stats}")

    # 3. Call format stage via context.call()
    print("[analyze] Calling format stage...")
    format_result = context.call(
        model_name="format",
        capability={"type": "format"},
        inputs={
            # BYTES: analysis data as JSON
            "analysis_json": [json.dumps(stats)],
            # BYTES: original text snippet
            "text_snippet": [original_text[:200] if original_text else ""],
            # FP32: key metrics
            "avg_token_length": [stats["avg_token_length"]],
            # INT32: counts
            "total_tokens": [stats["total_tokens"]],
            "unique_tokens": [stats["unique_tokens"]],
        }
    )
    print("[analyze] Format result received")

    # 4. Build response with the formatted report
    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )

    # Pass through the formatted report
    if "report" in format_result:
        report_data = format_result["report"]
        if isinstance(report_data, list) and len(report_data) > 0:
            if isinstance(report_data[0], bytes):
                report_bytes = report_data[0]
            else:
                report_bytes = report_data[0].encode('utf-8')
            response.add_output(
                name="report",
                datatype="BYTES",
                shape=[1],
                bytes_contents=[report_bytes],
            )

    return response


if __name__ == "__main__":
    print("Starting Worker B (analyze capability)...")
    app.run(host="0.0.0.0", port=50052)

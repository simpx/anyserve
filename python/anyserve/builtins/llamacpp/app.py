"""
llama.cpp AnyServe Worker Application

This module provides a built-in worker for serving GGUF models
using llama-cpp-python with native KServe protocol support.

Usage:
    anyserve run anyserve.builtins.llamacpp.app:create_app("/path/to/model.gguf") --port 8000

Or via CLI:
    anyserve serve /path/to/model.gguf --port 8000
"""

import anyserve
from anyserve import ModelInferRequest, ModelInferResponse, Context, Stream

from .config import LlamaCppConfig
from .engine import LlamaCppEngine

# Global engine instance (initialized when app is created)
_engine: LlamaCppEngine = None
_config: LlamaCppConfig = None


def _set_engine(engine: LlamaCppEngine, config: LlamaCppConfig):
    """设置全局 engine（由 factory 调用）"""
    global _engine, _config
    _engine = engine
    _config = config


def create_app(
    model_path: str,
    name: str = None,
    n_ctx: int = 2048,
    n_gpu_layers: int = -1,
    n_batch: int = 512,
    n_threads: int = None,
    **kwargs
) -> anyserve.AnyServe:
    """
    Create an AnyServe app for llama.cpp model.

    Args:
        model_path: Path to the GGUF model file
        name: Model name for API (defaults to filename)
        n_ctx: Context window size
        n_gpu_layers: Number of GPU layers (-1 for all)
        n_batch: Batch size for prompt processing
        n_threads: Number of CPU threads
        **kwargs: Additional config options

    Returns:
        AnyServe app instance with registered capability handlers
    """
    global _engine, _config
    from pathlib import Path

    # Create config
    _config = LlamaCppConfig(
        model_path=model_path,
        name=name or Path(model_path).stem,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        n_batch=n_batch,
        n_threads=n_threads,
        **kwargs
    )

    # Create and load engine
    print(f"[LlamaCpp] Loading model from {model_path}...")
    _engine = LlamaCppEngine(_config)
    _engine.load()
    print(f"[LlamaCpp] Model loaded successfully: {_config.name}")

    return app


# Create the AnyServe app
app = anyserve.AnyServe()


@app.capability(type="generate", model="llamacpp")
def generate_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
    """
    Text generation capability (non-streaming).

    KServe Protocol:
        Input:
            - name: "prompt", datatype: "BYTES", shape: [1]
            - name: "max_tokens" (optional), datatype: "INT32", shape: [1]
            - name: "temperature" (optional), datatype: "FP32", shape: [1]
            - name: "top_p" (optional), datatype: "FP32", shape: [1]
            - name: "top_k" (optional), datatype: "INT32", shape: [1]

        Output:
            - name: "text", datatype: "BYTES", shape: [1]
            - name: "model", datatype: "BYTES", shape: [1]
    """
    global _engine, _config

    if _engine is None:
        return ModelInferResponse(
            model_name=request.model_name,
            id=request.id,
            error="Model not loaded"
        )

    # Extract prompt from input
    prompt_input = request.get_input("prompt")
    if prompt_input is None:
        return ModelInferResponse(
            model_name=request.model_name,
            id=request.id,
            error="Missing required input 'prompt'"
        )

    prompt = prompt_input.bytes_contents[0].decode("utf-8") if prompt_input.bytes_contents else ""

    # Extract optional parameters
    max_tokens = _get_int_param(request, "max_tokens", _config.max_tokens)
    temperature = _get_float_param(request, "temperature", _config.temperature)
    top_p = _get_float_param(request, "top_p", _config.top_p)
    top_k = _get_int_param(request, "top_k", _config.top_k)

    print(f"[LlamaCpp] Generating for prompt: {prompt[:50]}...")

    # Generate text
    generated_text = _engine.generate(
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
    )

    # Build response
    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )
    response.add_output(
        name="text",
        datatype="BYTES",
        shape=[1],
        bytes_contents=[generated_text.encode("utf-8")],
    )
    response.add_output(
        name="model",
        datatype="BYTES",
        shape=[1],
        bytes_contents=[_config.name.encode("utf-8")],
    )

    return response


@app.capability(type="generate_stream", model="llamacpp", stream=True)
def generate_stream_handler(request: ModelInferRequest, context: Context, stream: Stream):
    """
    Streaming text generation capability.

    KServe Protocol (Streaming):
        Input: Same as generate
        Output (per chunk):
            - name: "token", datatype: "BYTES", shape: [1]
            - name: "finish_reason", datatype: "BYTES", shape: [1]  # null, stop, length
    """
    global _engine, _config

    if _engine is None:
        stream.error("Model not loaded")
        return

    # Extract prompt from input
    prompt_input = request.get_input("prompt")
    if prompt_input is None:
        stream.error("Missing required input 'prompt'")
        return

    prompt = prompt_input.bytes_contents[0].decode("utf-8") if prompt_input.bytes_contents else ""

    # Extract optional parameters
    max_tokens = _get_int_param(request, "max_tokens", _config.max_tokens)
    temperature = _get_float_param(request, "temperature", _config.temperature)
    top_p = _get_float_param(request, "top_p", _config.top_p)
    top_k = _get_int_param(request, "top_k", _config.top_k)

    print(f"[LlamaCpp] Streaming for prompt: {prompt[:50]}...")

    # Import proto for streaming response
    from anyserve._proto import grpc_predict_v2_pb2

    # Stream tokens
    for token in _engine.generate_stream(
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
    ):
        # Create streaming response
        response = grpc_predict_v2_pb2.ModelStreamInferResponse()
        response.infer_response.model_name = request.model_name
        response.infer_response.id = request.id

        # Add token output
        output = response.infer_response.outputs.add()
        output.name = "token"
        output.datatype = "BYTES"
        output.shape.append(1)
        output.contents.bytes_contents.append(token.encode("utf-8"))

        # Add finish_reason (null for ongoing)
        finish_output = response.infer_response.outputs.add()
        finish_output.name = "finish_reason"
        finish_output.datatype = "BYTES"
        finish_output.shape.append(1)
        finish_output.contents.bytes_contents.append(b"null")

        stream.send(response)

    # Send final response with finish_reason
    final_response = grpc_predict_v2_pb2.ModelStreamInferResponse()
    final_response.infer_response.model_name = request.model_name
    final_response.infer_response.id = request.id

    token_output = final_response.infer_response.outputs.add()
    token_output.name = "token"
    token_output.datatype = "BYTES"
    token_output.shape.append(1)
    token_output.contents.bytes_contents.append(b"")

    finish_output = final_response.infer_response.outputs.add()
    finish_output.name = "finish_reason"
    finish_output.datatype = "BYTES"
    finish_output.shape.append(1)
    finish_output.contents.bytes_contents.append(b"stop")

    stream.send(final_response)


@app.capability(type="model_info", model="llamacpp")
def model_info_handler(request: ModelInferRequest, context: Context) -> ModelInferResponse:
    """
    Get model information.

    Output:
        - name: "model_name", datatype: "BYTES", shape: [1]
        - name: "n_ctx", datatype: "INT32", shape: [1]
    """
    global _config

    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id,
    )

    if _config:
        response.add_output(
            name="model_name",
            datatype="BYTES",
            shape=[1],
            bytes_contents=[_config.name.encode("utf-8")],
        )
        response.add_output(
            name="n_ctx",
            datatype="INT32",
            shape=[1],
            int_contents=[_config.n_ctx],
        )

    return response


def _get_int_param(request: ModelInferRequest, name: str, default: int) -> int:
    """Extract integer parameter from request."""
    inp = request.get_input(name)
    if inp and inp.int_contents:
        return inp.int_contents[0]
    return default


def _get_float_param(request: ModelInferRequest, name: str, default: float) -> float:
    """Extract float parameter from request."""
    inp = request.get_input(name)
    if inp and inp.fp32_contents:
        return inp.fp32_contents[0]
    return default

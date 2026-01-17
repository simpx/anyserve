"""
AnyServe serve command - Serve a llama.cpp model using AnyServe worker.

Usage:
    anyserve serve /models/llama-7b-chat.gguf
    anyserve serve /models/llama-7b-chat.gguf --name llama-7b --port 8000
    anyserve serve --config /etc/anyserve/model.yaml
"""

import os
import sys
from pathlib import Path

import click


@click.command()
@click.argument("model_path", type=click.Path(exists=True), required=False)
@click.option("--name", type=str, help="Model name for API")
@click.option("--n-ctx", type=int, default=2048, help="Context window size")
@click.option("--n-gpu-layers", type=int, default=-1, help="GPU layers (-1 for all)")
@click.option("--n-batch", type=int, default=512, help="Batch size")
@click.option("--n-threads", type=int, default=None, help="CPU threads")
@click.option("--port", type=int, default=8000, help="Server port")
@click.option("--host", type=str, default="0.0.0.0", help="Server host")
@click.option("--workers", type=int, default=1, help="Number of workers")
@click.option("--config", type=click.Path(exists=True), help="Config file path")
@click.option("--openai-port", type=int, default=None, help="OpenAI API port (disabled if not set)")
@click.option("--openai-host", type=str, default="0.0.0.0", help="OpenAI server host")
def serve_command(model_path, name, n_ctx, n_gpu_layers, n_batch, n_threads, port, host, workers, config, openai_port, openai_host):
    """Start anyserve with a llama.cpp model.

    This command runs a llama.cpp model using the AnyServe worker framework,
    exposing it via the KServe gRPC protocol.

    Example:
        anyserve serve /models/llama-7b.gguf --name llama-7b --port 8000

        # With embedded OpenAI-compatible API server
        anyserve serve /models/llama-7b.gguf --port 8000 --openai-port 8080
    """
    from anyserve.builtins.llamacpp import LlamaCppConfig

    # Load configuration
    if config:
        cfg = LlamaCppConfig.from_yaml(config)
        model_path = cfg.model_path
        name = name or cfg.name
        n_ctx = cfg.n_ctx
        n_gpu_layers = cfg.n_gpu_layers
        n_batch = cfg.n_batch
        n_threads = cfg.n_threads
        port = cfg.port
        host = cfg.host
        openai_port = openai_port or cfg.openai_port
        openai_host = openai_host or cfg.openai_host
    else:
        if not model_path:
            raise click.UsageError("Either model_path or --config is required")

    # Validate model path
    cfg = LlamaCppConfig(model_path=model_path)
    cfg.validate()

    # Infer model name from file name
    model_name = name or Path(model_path).stem

    click.echo(f"Starting AnyServe with llama.cpp model:")
    click.echo(f"  Model path: {model_path}")
    click.echo(f"  Model name: {model_name}")
    click.echo(f"  Context size: {n_ctx}")
    click.echo(f"  GPU layers: {n_gpu_layers}")
    click.echo(f"  KServe: {host}:{port}")
    click.echo(f"  Workers: {workers}")
    if openai_port:
        click.echo(f"  OpenAI API: {openai_host}:{openai_port}")
    click.echo()

    # 设置环境变量（供 factory 读取）
    os.environ["ANYSERVE_LLAMACPP_MODEL_PATH"] = str(model_path)
    os.environ["ANYSERVE_LLAMACPP_NAME"] = model_name
    os.environ["ANYSERVE_LLAMACPP_N_CTX"] = str(n_ctx)
    os.environ["ANYSERVE_LLAMACPP_N_GPU_LAYERS"] = str(n_gpu_layers)
    os.environ["ANYSERVE_LLAMACPP_N_BATCH"] = str(n_batch)
    if n_threads:
        os.environ["ANYSERVE_LLAMACPP_N_THREADS"] = str(n_threads)

    # OpenAI server environment variables
    if openai_port:
        os.environ["ANYSERVE_LLAMACPP_OPENAI_PORT"] = str(openai_port)
        os.environ["ANYSERVE_LLAMACPP_OPENAI_HOST"] = openai_host
        # Use worker's gRPC port (ingress_port + 100) for streaming support
        grpc_port = port + 100
        os.environ["ANYSERVE_LLAMACPP_KSERVE_ENDPOINT"] = f"localhost:{grpc_port}"

    # Use the standard AnyServe server with factory mode
    from .run import AnyServeServer

    server = AnyServeServer(
        app="anyserve.builtins.llamacpp:create_app",
        factory=True,  # 使用 factory 模式
        host=host,
        port=port,
        workers=workers,
    )

    try:
        server.start()
    except KeyboardInterrupt:
        click.echo("\n[AnyServe] Received Ctrl+C, shutting down...")
    except Exception as e:
        click.echo(f"[AnyServe] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        server.stop()

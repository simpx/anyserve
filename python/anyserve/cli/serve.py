"""
AnyServe serve command - Serve a llama.cpp model.

Usage:
    anyserve serve /models/llama-7b-chat.gguf
    anyserve serve /models/llama-7b-chat.gguf --name llama-7b --port 8000
    anyserve serve --config /etc/anyserve/model.yaml
"""

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
@click.option("--config", type=click.Path(exists=True), help="Config file path")
def serve_command(model_path, name, n_ctx, n_gpu_layers, n_batch, n_threads, port, host, config):
    """Start anyserve with a llama.cpp model.

    Example:
        anyserve serve /models/llama-7b.gguf --name llama-7b --port 8000
    """
    from anyserve.builtins.llamacpp import LlamaCppConfig, create_server

    # Load configuration
    if config:
        cfg = LlamaCppConfig.from_yaml(config)
    else:
        if not model_path:
            raise click.UsageError("Either model_path or --config is required")

        # Infer model name from file name
        model_name = name or Path(model_path).stem

        cfg = LlamaCppConfig(
            model_path=model_path,
            name=model_name,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            n_threads=n_threads,
            port=port,
            host=host,
        )

    cfg.validate()

    click.echo(f"Starting anyserve with model: {cfg.model_path}")
    click.echo(f"  Model name: {cfg.name}")
    click.echo(f"  Context size: {cfg.n_ctx}")
    click.echo(f"  GPU layers: {cfg.n_gpu_layers}")
    click.echo(f"  Host: {cfg.host}")
    click.echo(f"  Port: {cfg.port}")

    # Create and start the server
    server = create_server(cfg)
    server.run()

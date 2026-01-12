"""
AnyServe CLI - Command Line Interface

Usage:
    anyserve run app:main
    anyserve --version
"""

import click
import importlib
import sys


@click.group()
@click.version_option(version="0.1.0", prog_name="anyserve")
def main():
    """AnyServe - Capability-Oriented Serving Runtime"""
    pass


@main.command()
@click.argument("target")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", "-p", default=8000, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def run(target: str, host: str, port: int, reload: bool):
    """Run an anyserve application.
    
    TARGET: Module path in format 'module:app' (e.g., 'app:main')
    """
    if ":" not in target:
        click.echo(f"Error: Invalid target format '{target}'. Use 'module:app'", err=True)
        sys.exit(1)
    
    module_path, app_name = target.rsplit(":", 1)
    
    try:
        module = importlib.import_module(module_path)
        app = getattr(module, app_name)
    except ModuleNotFoundError:
        click.echo(f"Error: Module '{module_path}' not found", err=True)
        sys.exit(1)
    except AttributeError:
        click.echo(f"Error: '{app_name}' not found in module '{module_path}'", err=True)
        sys.exit(1)
    
    click.echo(f"Starting AnyServe on {host}:{port}")
    click.echo(f"Loading: {target}")
    
    # TODO: 实际启动 anyserve 服务
    # 目前先调用 app（假设是一个可调用对象或 anyserve 应用）
    if callable(app):
        app()
    else:
        click.echo(f"Running app: {app}")


if __name__ == "__main__":
    main()

"""
AnyServe CLI - Command line interface for AnyServe.

Usage:
    anyserve run app:app                    # Run a custom app
    anyserve serve /models/model.gguf       # Serve a llama.cpp model
"""

import click
from .run import run_command
from .serve import serve_command


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """anyserve - Capability-Oriented Serving Runtime for LLM inference."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Add subcommands
cli.add_command(run_command, name="run")
cli.add_command(serve_command, name="serve")


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()

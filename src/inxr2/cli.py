"""
CLI entry point for INXR2.

This module provides the command-line interface for the INXR2 application.
"""

import click


@click.group()
@click.version_option()
def main() -> None:
    """INXR2 - Cross-reference code browser for git repositories."""
    pass


@main.command()
def index() -> None:
    """Index repositories from configuration."""
    click.echo("Indexing not yet implemented.")


@main.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the FastAPI web server."""
    import uvicorn

    click.echo(f"Starting INXR2 API server on {host}:{port}")
    if reload:
        click.echo("Auto-reload enabled")

    uvicorn.run(
        "inxr2.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@main.command()
def status() -> None:
    """Show indexing status."""
    click.echo("Status not yet implemented.")


if __name__ == "__main__":
    main()

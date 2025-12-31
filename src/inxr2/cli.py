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
def serve() -> None:
    """Start the web server."""
    click.echo("Server not yet implemented.")


@main.command()
def status() -> None:
    """Show indexing status."""
    click.echo("Status not yet implemented.")


if __name__ == "__main__":
    main()

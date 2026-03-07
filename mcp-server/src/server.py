"""INXR2 MCP Server entry point.

Exposes INXR2 code intelligence as MCP tools for AI assistants.
Supports both stdio and SSE transports.
"""

from __future__ import annotations

import os
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.client import HttpInxr2Client, Inxr2Client
from src.tools import (
    find_references,
    go_to_definition,
    list_repositories,
    search_code,
    search_symbols,
)
from src.urls import get_frontend_url

# Registry of all tools
TOOLS = [
    list_repositories,
    find_references,
    go_to_definition,
    search_symbols,
    search_code,
]
TOOL_MAP = {tool.TOOL_NAME: tool for tool in TOOLS}


def create_server(client: Inxr2Client, frontend_url: str | None = None) -> Server:
    """Create an MCP server wired to the given INXR2 client."""
    server = Server("inxr2")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=tool.TOOL_NAME,
                description=tool.TOOL_DESCRIPTION,
                inputSchema=tool.TOOL_SCHEMA,
            )
            for tool in TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        tool_module = TOOL_MAP.get(name)
        if not tool_module:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        try:
            result = await tool_module.handle(
                client, arguments, frontend_url=frontend_url
            )
            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    return server


async def run_stdio(base_url: str, frontend_url: str | None = None) -> None:
    """Run the MCP server over stdio transport."""
    client = HttpInxr2Client(base_url)
    server = create_server(client, frontend_url=frontend_url)
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
    finally:
        await client.close()


def main() -> None:
    import asyncio

    base_url = os.environ.get("INXR2_API_URL", "http://localhost:8000")
    frontend_url = get_frontend_url()

    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport == "stdio":
        asyncio.run(run_stdio(base_url, frontend_url=frontend_url))
    elif transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.responses import Response
        from starlette.routing import Mount, Route

        client = HttpInxr2Client(base_url)
        server = create_server(client, frontend_url=frontend_url)
        sse = SseServerTransport("/messages/")

        async def handle_sse(request):  # type: ignore[no-untyped-def]
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await server.run(
                    streams[0], streams[1], server.create_initialization_options()
                )
            return Response()

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def lifespan(app):  # type: ignore[no-untyped-def]
            yield
            await client.close()

        app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
            lifespan=lifespan,
        )

        import uvicorn

        port = int(os.environ.get("MCP_PORT", "3000"))
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        print(f"Unknown transport: {transport}. Use 'stdio' or 'sse'.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

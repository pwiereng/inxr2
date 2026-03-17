"""INXR2 MCP Server entry point.

Exposes INXR2 code intelligence as MCP tools for AI assistants.
Supports both stdio and SSE transports.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.client import HttpInxr2Client, Inxr2Client
from src.tools import (
    find_dead_code,
    find_references,
    get_change_impact,
    get_file_structure,
    go_to_definition,
    list_repositories,
    review_helper,
    search_code,
    search_symbols,
)
from src.urls import get_frontend_url

_mcp_logger = logging.getLogger("inxr2.mcp")
_LOG_MCP_CALLS = os.getenv("LOG_MCP_CALLS", "true").lower() != "false"

# Registry of all tools
TOOLS = [
    list_repositories,
    find_dead_code,
    find_references,
    get_change_impact,
    get_file_structure,
    go_to_definition,
    review_helper,
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

    async def _ingest_mcp_call(
        name: str,
        arguments: dict,
        duration_ms: int,
        result_count: int | None,
        repository: str | None,
    ) -> None:
        """Fire-and-forget: write MCP tool call to the activity log DB via the API."""
        try:
            await client.post(
                "/api/activity/ingest",
                {
                    "source": "mcp",
                    "tool_or_path": name,
                    "params": arguments,
                    "repository": repository,
                    "duration_ms": duration_ms,
                    "result_count": result_count,
                },
            )
        except Exception:
            pass  # Never let logging failure affect tool response

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        tool_module = TOOL_MAP.get(name)
        if not tool_module:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        start = time.monotonic()
        try:
            result = await tool_module.handle(
                client, arguments, frontend_url=frontend_url
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            result_count: int | None = None
            try:
                parsed = json.loads(result)
                if isinstance(parsed, list):
                    result_count = len(parsed)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

            repository: str | None = arguments.get("repository") or arguments.get(
                "repo"
            )

            if _LOG_MCP_CALLS:
                log_data = {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "source": "mcp",
                    "tool": name,
                    "args": arguments,
                    "duration_ms": duration_ms,
                    "result_count": result_count,
                }
                _mcp_logger.info(json.dumps(log_data))

            if _LOG_MCP_CALLS:
                asyncio.ensure_future(
                    _ingest_mcp_call(
                        name, arguments, duration_ms, result_count, repository
                    )
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

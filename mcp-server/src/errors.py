"""Custom exceptions for MCP tool handlers."""

from __future__ import annotations


class McpToolError(Exception):
    """Raised by tool handlers to signal a user-visible error.

    The server wraps these in a CallToolResult with isError=True so that MCP
    clients can distinguish errors from valid (possibly empty) results.
    """

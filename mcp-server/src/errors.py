"""Custom exceptions for MCP tool handlers."""

from __future__ import annotations


class McpToolError(Exception):
    """Raised by tool handlers to signal a user-visible error.

    The server wraps these in a CallToolResult with isError=True so that MCP
    clients can distinguish errors from valid (possibly empty) results.
    """


class ApiNotFoundError(Exception):
    """The INXR2 API answered 404 Not Found.

    Carries the API's ``detail`` message, so tools can turn a 404 into an
    actionable error instead of httpx's raw "Client error '404 Not Found'".
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def path_not_found_error(
    error: ApiNotFoundError,
    path: str,
    *,
    branch: str,
    commit: str | None = None,
) -> McpToolError:
    """Explain a 404 from an endpoint that looks up ``path`` (issue #557).

    ``branch`` is the branch whose head was searched (the default branch when
    the caller passed none). Only the API's FileNotFound messages, which all
    start with "File ", mean the path itself is missing; any other 404 (an
    unknown branch or commit) keeps the API's own detail.
    """
    if not error.detail.startswith("File "):
        return McpToolError(error.detail)
    if commit:
        return McpToolError(f"`{path}` is not present at commit `{commit}`.")
    return McpToolError(
        f"`{path}` is not present at the head of `{branch}` "
        "(it may have been deleted or renamed). "
        "Pass `commit` to look at an older version."
    )

"""URL builder for INXR2 frontend browse links."""

from __future__ import annotations

import os
from urllib.parse import quote, urlencode


def get_frontend_url() -> str | None:
    """Return the frontend base URL from environment, or None if not set."""
    return os.environ.get("INXR2_FRONTEND_URL") or None


def build_browse_url(
    base_url: str,
    repo_name: str,
    file_path: str,
    line: int | None = None,
    branch: str | None = None,
    commit: str | None = None,
) -> str:
    """Build a browse URL for the INXR2 frontend.

    Pattern: {base_url}/browse/{repo}/{path}?line=N&branch=B&commit=C
    """
    # Quote path segments but preserve slashes
    path = f"/browse/{quote(repo_name, safe='')}/{quote(file_path, safe='/')}"
    url = base_url.rstrip("/") + path

    params: dict[str, str] = {}
    if line is not None:
        params["line"] = str(line)
    if branch is not None:
        params["branch"] = branch
    if commit is not None:
        params["commit"] = commit

    if params:
        url += "?" + urlencode(params)

    return url

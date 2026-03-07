"""Fake INXR2 client for testing — no HTTP calls, returns canned data."""

from __future__ import annotations

from typing import Any

from src.client import Inxr2Client


class FakeInxr2Client(Inxr2Client):
    """In-memory fake that simulates INXR2 API responses.

    Populate with data via the add_* methods, then pass to tool handlers.
    """

    def __init__(self) -> None:
        self._repositories: list[dict[str, Any]] = []
        self._symbols: list[dict[str, Any]] = []
        self._references: dict[int, list[dict[str, Any]]] = {}  # symbol_id -> refs
        self._search_results: list[dict[str, Any]] = []
        self._branches: dict[int, list[dict[str, Any]]] = {}  # repo_id -> branches
        self._stats: dict[int, dict[str, Any]] = {}  # repo_id -> stats
        self._commits: dict[str, list[dict[str, Any]]] = {}  # repo_name -> commits
        self._changed_files: dict[str, list[dict[str, Any]]] = (
            {}
        )  # commit_hash -> files

    # --- Data population helpers ---

    def add_repository(
        self,
        repo_id: int,
        name: str,
        default_branch: str = "main",
        indexed_branches: list[dict[str, Any]] | None = None,
    ) -> None:
        self._repositories.append(
            {"id": repo_id, "name": name, "default_branch": default_branch}
        )
        if indexed_branches is not None:
            self._branches[repo_id] = indexed_branches

    def add_symbol(
        self,
        symbol_id: int,
        name: str,
        kind: str = "function",
        file_path: str = "src/main.py",
        start_line: int = 1,
        repository_id: int = 1,
        qualified_name: str | None = None,
        signature: str | None = None,
        docstring: str | None = None,
    ) -> None:
        self._symbols.append(
            {
                "id": symbol_id,
                "name": name,
                "kind": kind,
                "file_path": file_path,
                "start_line": start_line,
                "repository_id": repository_id,
                "qualified_name": qualified_name,
                "signature": signature,
                "docstring": docstring,
                "start_column": 0,
                "end_line": start_line + 5,
                "end_column": 0,
                "file_id": symbol_id,
            }
        )

    def add_reference(
        self,
        symbol_id: int,
        file_path: str,
        line: int,
        ref_type: str = "usage",
        text: str = "",
    ) -> None:
        if symbol_id not in self._references:
            self._references[symbol_id] = []
        self._references[symbol_id].append(
            {
                "id": len(self._references[symbol_id]) + 1,
                "source_file_id": 1,
                "source_file_path": file_path,
                "source_line": line,
                "source_column": 0,
                "target_symbol_id": symbol_id,
                "reference_text": text,
                "reference_type": ref_type,
            }
        )

    def set_stats(
        self,
        repo_id: int,
        is_stale: bool = False,
        last_indexed_commit: str | None = None,
        last_indexed_at: str | None = None,
    ) -> None:
        self._stats[repo_id] = {
            "is_stale": is_stale,
            "last_indexed_commit": last_indexed_commit,
            "last_indexed_at": last_indexed_at,
        }

    def add_commit(
        self,
        repo_name: str,
        full_hash: str,
        message: str = "",
        author_name: str = "Test Author",
    ) -> None:
        if repo_name not in self._commits:
            self._commits[repo_name] = []
        self._commits[repo_name].append(
            {
                "hash": full_hash,
                "short_hash": full_hash[:7],
                "message": message,
                "author_name": author_name,
                "author_email": "test@example.com",
                "commit_date": "2026-03-01T12:00:00",
                "is_indexed": True,
                "tags": [],
                "is_branch_specific": False,
                "is_merge_base": False,
            }
        )

    def add_changed_file(
        self,
        commit_hash: str,
        file_path: str,
        file_id: int = 1,
        language: str | None = None,
    ) -> None:
        if commit_hash not in self._changed_files:
            self._changed_files[commit_hash] = []
        self._changed_files[commit_hash].append(
            {
                "name": file_path.rsplit("/", 1)[-1],
                "path": file_path,
                "type": "file",
                "file_id": file_id,
                "language": language,
                "children": None,
            }
        )

    def add_search_result(
        self,
        file_path: str,
        line: int,
        content: str,
        repository_name: str = "test-repo",
        headline: str | None = None,
    ) -> None:
        # Look up repository_id from name, default to 1
        repo_id = 1
        for repo in self._repositories:
            if repo["name"] == repository_name:
                repo_id = repo["id"]
                break
        self._search_results.append(
            {
                "id": len(self._search_results) + 1,
                "repository_id": repo_id,
                "repository_name": repository_name,
                "file_path": file_path,
                "source_line": line,
                "source_end_line": line,
                "source_type": "file_content",
                "content": content,
                "content_type": None,
                "language": None,
                "commit_hash": None,
                "branch": None,
                "rank": 1.0,
                "headline": headline,
            }
        )

    # --- Inxr2Client interface ---

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}

        # GET /api/commits
        if path == "/api/commits":
            repo_name = params.get("repo", "")
            commits = self._commits.get(repo_name, [])
            limit = int(params.get("limit", 50))
            return {"commits": commits[:limit], "total": len(commits)}

        # GET /api/repositories/by-name/{name}/tree
        if "/tree" in path and "/repositories/by-name/" in path:
            parts = path.split("/")
            # /api/repositories/by-name/{name}/tree
            repo_name = parts[4]
            commit_hash = params.get("commit", "")
            changed_only = params.get("changed_only") in ("true", True)
            if changed_only and commit_hash:
                files = self._changed_files.get(commit_hash, [])
            else:
                files = []
            return {
                "repository_id": 1,
                "repository_name": repo_name,
                "root": files,
                "total_files": len(files),
                "total_directories": 0,
            }

        # GET /api/repositories
        if path == "/api/repositories":
            return self._repositories

        # GET /api/repositories/{id}/branches
        if path.endswith("/branches") and "/repositories/" in path:
            parts = path.split("/")
            repo_id = int(parts[3])  # /api/repositories/{id}/branches
            return {"branches": self._branches.get(repo_id, [])}

        # GET /api/repositories/{id}/stats
        if path.endswith("/stats") and "/repositories/" in path:
            parts = path.split("/")
            repo_id = int(parts[3])  # /api/repositories/{id}/stats
            return self._stats.get(
                repo_id,
                {
                    "is_stale": False,
                    "last_indexed_commit": None,
                    "last_indexed_at": None,
                },
            )

        # GET /api/repositories/by-name/{name}
        if path.startswith("/api/repositories/by-name/"):
            name = path.split("/")[-1]
            for repo in self._repositories:
                if repo["name"] == name:
                    return repo
            raise Exception(f"Repository not found: {name}")

        # GET /api/symbols/by-name/{name}
        if path.startswith("/api/symbols/by-name/"):
            name = path.split("/")[-1]
            byname_repo_id: Any = params.get("repository_id")
            matches = [s for s in self._symbols if s["name"] == name]
            if byname_repo_id is not None:
                matches = [
                    s for s in matches if s["repository_id"] == int(byname_repo_id)
                ]
            return {"items": matches, "total": len(matches), "limit": 50, "offset": 0}

        # GET /api/symbols/{id}/references
        if "/references" in path and "/symbols/" in path:
            parts = path.split("/")
            symbol_id = int(parts[3])  # /api/symbols/{id}/references
            refs = self._references.get(symbol_id, [])
            return {"items": refs, "total": len(refs), "symbol_name": ""}

        # GET /api/symbols
        if path == "/api/symbols":
            import re

            query = params.get("q", "")
            mode = params.get("mode")
            kind = params.get("kind")
            sym_repo_id: Any = params.get("repository_id")
            limit = int(params.get("limit", 50))

            if mode == "regex":
                pattern = re.compile(query)
                matches = [s for s in self._symbols if pattern.search(s["name"])]
            else:
                matches = [
                    s for s in self._symbols if query.lower() in s["name"].lower()
                ]
            if kind:
                matches = [s for s in matches if s["kind"] == kind]
            if sym_repo_id is not None:
                matches = [s for s in matches if s["repository_id"] == int(sym_repo_id)]
            total = len(matches)
            matches = matches[:limit]
            return {
                "items": matches,
                "total": total,
                "limit": limit,
                "offset": 0,
            }

        # GET /api/search/text
        if path == "/api/search/text":
            query = params.get("q", "")
            mode = params.get("mode", "keyword")
            limit = int(params.get("limit", 20))
            search_repo_id: Any = params.get("repository_id")
            matches = list(self._search_results)
            if search_repo_id is not None:
                matches = [
                    r for r in matches if r.get("repository_id") == int(search_repo_id)
                ]
            total = len(matches)
            results = matches[:limit]
            return {
                "results": results,
                "total": total,
                "query": query,
                "mode": mode,
                "limit": limit,
                "offset": 0,
            }

        raise Exception(f"Unhandled path in FakeInxr2Client: {path}")

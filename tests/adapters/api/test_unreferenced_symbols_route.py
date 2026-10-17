"""Tests for GET /api/symbols/unreferenced (issue #548).

Uses a minimal FastAPI app whose use case is wired to in-memory fakes.
"""

from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from inxr2.adapters.api.routes import symbols
from inxr2.application.use_cases.symbols import FindDeadCodeUseCase
from inxr2.domain.entities import Commit, File, Reference, Symbol
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind
from inxr2.infrastructure.dependencies import get_find_dead_code_use_case
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
)


async def _app(symbol_count: int) -> FastAPI:
    commit_repo = InMemoryCommitRepository()
    commit_repo._commits[1] = Commit(
        id=1,
        repository_id=1,
        commit_hash=CommitHash("abc123def456"),
        author_date=datetime(2025, 1, 1),
        commit_date=datetime(2025, 1, 1),
    )
    file_repo = InMemoryFileRepository(commit_repo=commit_repo)
    file_repo.add(
        File(
            id=1,
            repository_id=1,
            path="App.swift",
            content_hash="h1",
            size_bytes=1,
            language="swift",
        )
    )
    symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
    for i in range(symbol_count):
        await symbol_repo.save(
            Symbol(
                id=i + 1,
                repository_id=1,
                file_id=1,
                name=f"sym_{i:03d}",
                kind=SymbolKind.FUNCTION,
                start_line=i + 1,
                start_column=0,
                end_line=i + 1,
                end_column=1,
            )
        )
    await symbol_repo.save(
        Symbol(
            id=symbol_count + 1,
            repository_id=1,
            file_id=1,
            name="CarbingoApp",
            kind=SymbolKind.STRUCT,
            start_line=1000,
            start_column=0,
            end_line=1001,
            end_column=0,
            metadata={"entry_point": "@main"},
        )
    )
    ref_repo = InMemoryReferenceRepository(
        symbol_repo=symbol_repo, file_repo=file_repo, commit_repo=commit_repo
    )
    use_case = FindDeadCodeUseCase(
        reference_repo=ref_repo, file_repo=file_repo, commit_repo=commit_repo
    )
    app = FastAPI()
    app.dependency_overrides[get_find_dead_code_use_case] = lambda: use_case
    app.include_router(symbols.router, prefix="/api")
    return app


async def _branch_app() -> FastAPI:
    """main has a.py (calls helper) + b.py; feature's head has b.py only."""
    commit_repo = InMemoryCommitRepository()
    for commit_id, branch in ((1, "main"), (2, "feature")):
        commit_repo._commits[commit_id] = Commit(
            id=commit_id,
            repository_id=1,
            commit_hash=CommitHash(f"{commit_id}" * 12),
            author_date=datetime(2025, 1, commit_id),
            commit_date=datetime(2025, 1, commit_id),
        )
        await commit_repo.link_commit_to_branch(1, commit_id, branch)
    file_repo = InMemoryFileRepository(commit_repo=commit_repo)
    for file_id, path in ((1, "a.py"), (2, "b.py")):
        file_repo.add(
            File(
                id=file_id,
                repository_id=1,
                path=path,
                content_hash=f"h{file_id}",
                size_bytes=1,
                language="python",
            )
        )
    for commit_id, file_id in ((1, 1), (1, 2), (2, 2)):
        await file_repo.link_file_to_commit(file_id, commit_id)
    symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
    for symbol_id, file_id, name, kind in (
        (1, 1, "main", SymbolKind.FUNCTION),
        (2, 2, "helper", SymbolKind.FUNCTION),
        (3, 2, "Widget", SymbolKind.CLASS),
    ):
        await symbol_repo.save(
            Symbol(
                id=symbol_id,
                repository_id=1,
                file_id=file_id,
                name=name,
                kind=kind,
                start_line=symbol_id,
                start_column=0,
                end_line=symbol_id,
                end_column=1,
            )
        )
    ref_repo = InMemoryReferenceRepository(
        symbol_repo=symbol_repo, file_repo=file_repo, commit_repo=commit_repo
    )
    await ref_repo.save(
        Reference(
            repository_id=1,
            source_file_id=1,
            source_line=1,
            source_column=0,
            source_end_column=6,
            reference_text="helper",
            reference_type=ReferenceType.CALL,
        )
    )
    use_case = FindDeadCodeUseCase(
        reference_repo=ref_repo, file_repo=file_repo, commit_repo=commit_repo
    )
    app = FastAPI()
    app.dependency_overrides[get_find_dead_code_use_case] = lambda: use_case
    app.include_router(symbols.router, prefix="/api")
    return app


async def _get(app: FastAPI, params: dict[str, Any]) -> Any:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get("/api/symbols/unreferenced", params=params)


@pytest.mark.asyncio
class TestUnreferencedSymbolsRoute:
    async def test_reports_full_coverage_and_pages(self) -> None:
        app = await _app(symbol_count=250)

        response = await _get(app, {"repository_id": 1, "limit": 100, "offset": 200})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 250
        assert body["scanned"] == 251
        assert body["entry_points_excluded"] == 1
        assert (body["limit"], body["offset"]) == (100, 200)
        assert [i["name"] for i in body["items"]] == [
            f"sym_{i:03d}" for i in range(200, 250)
        ]
        assert body["items"][0]["file_path"] == "App.swift"

    async def test_repository_id_is_required(self) -> None:
        app = await _app(symbol_count=1)

        response = await _get(app, {})

        assert response.status_code == 422

    async def test_unknown_commit_returns_422(self) -> None:
        app = await _app(symbol_count=1)

        response = await _get(app, {"repository_id": 1, "commit": "deadbeef"})

        assert response.status_code == 422
        assert "not found" in response.json()["detail"]

    @pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 501}, {"offset": -1}])
    async def test_paging_bounds_are_enforced(self, params: dict[str, int]) -> None:
        app = await _app(symbol_count=1)

        response = await _get(app, {"repository_id": 1, **params})

        assert response.status_code == 422

    async def test_kind_filters_results(self) -> None:
        app = await _branch_app()

        response = await _get(app, {"repository_id": 1, "kind": "class"})

        assert [i["name"] for i in response.json()["items"]] == ["Widget"]
        assert response.json()["scanned"] == 1

    async def test_branch_scopes_results(self) -> None:
        app = await _branch_app()

        on_main = await _get(app, {"repository_id": 1})
        on_feature = await _get(app, {"repository_id": 1, "branch": "feature"})

        assert [i["name"] for i in on_main.json()["items"]] == ["main", "Widget"]
        # helper's only caller (a.py) is not on feature
        assert [i["name"] for i in on_feature.json()["items"]] == [
            "helper",
            "Widget",
        ]

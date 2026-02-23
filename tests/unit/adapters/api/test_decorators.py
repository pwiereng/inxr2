"""Tests for API decorator functions."""

import pytest
from fastapi import HTTPException

from inxr2.adapters.api.decorators import handle_file_resolution_errors
from inxr2.domain.exceptions import CommitNotFound, FileNotFound, RepositoryNotFound


class TestHandleFileResolutionErrors:
    @pytest.mark.asyncio
    async def test_passes_through_on_success(self) -> None:
        @handle_file_resolution_errors
        async def handler() -> str:
            return "ok"

        result = await handler()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_converts_repository_not_found(self) -> None:
        @handle_file_resolution_errors
        async def handler() -> str:
            raise RepositoryNotFound("test-repo")

        with pytest.raises(HTTPException) as exc_info:
            await handler()

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Repository not found"

    @pytest.mark.asyncio
    async def test_converts_file_not_found(self) -> None:
        @handle_file_resolution_errors
        async def handler() -> str:
            raise FileNotFound("src/main.py", repository_name="repo")

        with pytest.raises(HTTPException) as exc_info:
            await handler()

        assert exc_info.value.status_code == 404
        assert "src/main.py" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_converts_commit_not_found(self) -> None:
        @handle_file_resolution_errors
        async def handler() -> str:
            raise CommitNotFound(commit_hash="abc123")

        with pytest.raises(HTTPException) as exc_info:
            await handler()

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Commit not found"

    @pytest.mark.asyncio
    async def test_does_not_catch_other_exceptions(self) -> None:
        @handle_file_resolution_errors
        async def handler() -> str:
            raise ValueError("something else")

        with pytest.raises(ValueError, match="something else"):
            await handler()

    @pytest.mark.asyncio
    async def test_preserves_exception_chain(self) -> None:
        @handle_file_resolution_errors
        async def handler() -> str:
            raise RepositoryNotFound("test-repo")

        with pytest.raises(HTTPException) as exc_info:
            await handler()

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, RepositoryNotFound)

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self) -> None:
        @handle_file_resolution_errors
        async def handler(a: int, b: str, c: bool = False) -> str:
            return f"{a}-{b}-{c}"

        result = await handler(1, "two", c=True)
        assert result == "1-two-True"

    @pytest.mark.asyncio
    async def test_preserves_function_name(self) -> None:
        @handle_file_resolution_errors
        async def my_handler() -> str:
            return "ok"

        assert my_handler.__name__ == "my_handler"

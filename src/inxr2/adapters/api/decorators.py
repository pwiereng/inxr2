"""Shared decorators for API route handlers."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from fastapi import HTTPException

from ...domain.exceptions import CommitNotFound, FileNotFound, RepositoryNotFound

P = ParamSpec("P")
T = TypeVar("T")


def handle_file_resolution_errors(
    func: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, Coroutine[Any, Any, T]]:
    """Decorator that converts file resolution domain exceptions to HTTP errors.

    Catches RepositoryNotFound, FileNotFound, and CommitNotFound exceptions
    and raises the corresponding HTTPException with a 404 status code.
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except RepositoryNotFound as e:
            raise HTTPException(status_code=404, detail="Repository not found") from e
        except FileNotFound as e:
            raise HTTPException(status_code=404, detail=e.message) from e
        except CommitNotFound as e:
            raise HTTPException(status_code=404, detail="Commit not found") from e

    return wrapper

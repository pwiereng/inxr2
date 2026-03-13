"""Centralized exception-to-HTTP-response mapping.

Registers FastAPI exception handlers that convert domain exceptions
to appropriate HTTP error responses, eliminating duplicated try/except
blocks across route files.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ...application.use_cases.files import BinaryFileError, RepositoryPathNotFoundError
from ...domain.exceptions import (
    CommitNotFound,
    FileNotFound,
    RepositoryNotFound,
    SymbolNotFound,
)

logger = logging.getLogger(__name__)


async def _repository_not_found_handler(
    request: Request, exc: RepositoryNotFound
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Repository not found"})


async def _file_not_found_handler(request: Request, exc: FileNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


async def _commit_not_found_handler(
    request: Request, exc: CommitNotFound
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Commit not found"})


async def _symbol_not_found_handler(
    request: Request, exc: SymbolNotFound
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Symbol not found"})


async def _binary_file_handler(request: Request, exc: BinaryFileError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": "File is binary and cannot be displayed as text"},
    )


async def _repository_path_not_found_handler(
    request: Request, exc: RepositoryPathNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain exception handlers on the FastAPI app."""
    app.add_exception_handler(RepositoryNotFound, _repository_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(FileNotFound, _file_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(CommitNotFound, _commit_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(SymbolNotFound, _symbol_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(BinaryFileError, _binary_file_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RepositoryPathNotFoundError, _repository_path_not_found_handler)  # type: ignore[arg-type]

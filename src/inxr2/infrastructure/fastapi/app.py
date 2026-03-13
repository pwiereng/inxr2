"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI app

    TODO: Add router registration
    TODO: Add middleware configuration
    TODO: Add error handlers
    TODO: Add dependency injection
    """
    app = FastAPI(
        title="INXR2",
        description="Cross-reference code browser for git repositories",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server (main)
            "http://localhost:5183",  # Vite dev server (worktree slot 1)
            "http://localhost:5193",  # Vite dev server (worktree slot 2)
            "http://localhost:5203",  # Vite dev server (worktree slot 3)
        ],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    # Initialize database
    from ..database import init_database

    init_database()

    # Register routers
    from ...adapters.api.routes import (
        commits,
        files,
        indexing,
        repositories,
        search,
        symbols,
    )

    app.include_router(repositories.router, prefix="/api")
    app.include_router(indexing.router, prefix="/api")
    app.include_router(symbols.router, prefix="/api")
    app.include_router(files.router, prefix="/api")
    app.include_router(commits.router, prefix="/api")
    app.include_router(search.router, prefix="/api")

    # Health check endpoint
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    # Register centralized exception handlers
    from ...adapters.api.exception_handlers import register_exception_handlers

    register_exception_handlers(app)

    return app

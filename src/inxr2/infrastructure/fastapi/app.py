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

    # TODO: Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:8000",  # Production
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize database
    from ..database import init_database

    init_database()

    # Register routers
    from ...adapters.api.routes import files, indexing, repositories, symbols

    app.include_router(repositories.router, prefix="/api")
    app.include_router(indexing.router, prefix="/api")
    app.include_router(symbols.router, prefix="/api")
    app.include_router(files.router, prefix="/api")

    # Health check endpoint
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    # TODO: Add error handlers

    return app

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

    # TODO: Register routers
    # app.include_router(symbol_router, prefix="/api/symbols")
    # app.include_router(search_router, prefix="/api/search")

    # TODO: Add error handlers

    return app

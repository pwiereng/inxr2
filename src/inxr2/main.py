"""
FastAPI application entry point for INXR2.

This module provides the main FastAPI application with REST API endpoints.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Create FastAPI app instance
app = FastAPI(
    title="INXR2",
    description="Cross-reference code browser for git repositories",
    version="0.1.0",
)

# Configure CORS to allow frontend to call API
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

# Serve static frontend files if they exist (production mode)
# Try multiple locations for frontend dist
FRONTEND_DIST_LOCATIONS = [
    Path("/app/frontend/dist"),  # Production container location
    Path(__file__).parent.parent.parent / "frontend" / "dist",  # Development location
]
FRONTEND_DIST = None
for location in FRONTEND_DIST_LOCATIONS:
    if location.exists():
        FRONTEND_DIST = location
        break

if FRONTEND_DIST and (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/api")
async def api_root() -> dict[str, str]:
    """API root endpoint - returns welcome message."""
    return {
        "message": "Welcome to INXR2 API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "inxr2-api"}


@app.get("/api/hello")
async def hello(name: str = "World") -> dict[str, str]:
    """Hello world endpoint with optional name parameter."""
    return {"message": f"Hello, {name}!", "from": "INXR2 Backend"}


# Serve frontend index.html for all non-API routes (SPA support)
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str) -> FileResponse:
    """Serve the frontend application for all non-API routes."""
    if FRONTEND_DIST.exists():
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
    # If frontend not built, return API info
    return {"message": "Frontend not built. API available at /api/*", "docs": "/docs"}

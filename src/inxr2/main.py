"""
FastAPI application entry point for INXR2.

This module provides the main FastAPI application with REST API endpoints.
"""

from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .infrastructure.fastapi.app import create_app

# Create app using factory function
app = create_app()

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
    app.mount(
        "/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets"
    )


# Serve frontend index.html for all non-API routes (SPA support)
@app.get("/{full_path:path}", response_model=None)
async def serve_frontend(full_path: str) -> FileResponse | dict[str, str]:
    """Serve the frontend application for all non-API routes."""
    if FRONTEND_DIST and FRONTEND_DIST.exists():
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
    # If frontend not built, return API info
    return {"message": "Frontend not built. API available at /api/*", "docs": "/docs"}

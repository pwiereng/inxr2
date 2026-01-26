"""Tests for FastAPI application factory."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from inxr2.infrastructure.fastapi.app import create_app


class TestCreateApp:
    """Tests for create_app function."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create app instance for testing."""
        return create_app()

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_creates_fastapi_app(self, app: FastAPI) -> None:
        """create_app should return a FastAPI instance."""
        assert isinstance(app, FastAPI)

    def test_app_title(self, app: FastAPI) -> None:
        """App should have correct title."""
        assert app.title == "INXR2"

    def test_app_description(self, app: FastAPI) -> None:
        """App should have correct description."""
        assert "Cross-reference code browser" in app.description

    def test_app_version(self, app: FastAPI) -> None:
        """App should have version set."""
        assert app.version == "0.1.0"

    def test_cors_middleware_configured(self, app: FastAPI) -> None:
        """App should have CORS middleware configured."""
        # Check that CORSMiddleware is in the middleware stack
        # The middleware is wrapped, so we check via the app's middleware attribute
        has_cors = any("CORSMiddleware" in str(m) for m in app.user_middleware)
        assert has_cors

    def test_health_endpoint(self, client: TestClient) -> None:
        """App should have /api/health endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_repositories_router_registered(self, app: FastAPI) -> None:
        """App should have repositories router registered."""
        routes = [getattr(route, "path", "") for route in app.routes]
        # Check for at least one repository endpoint
        assert any("/api/repositories" in route for route in routes)

    def test_indexing_router_registered(self, app: FastAPI) -> None:
        """App should have indexing router registered."""
        routes = [getattr(route, "path", "") for route in app.routes]
        assert any("/api/index" in route for route in routes)

    def test_symbols_router_registered(self, app: FastAPI) -> None:
        """App should have symbols router registered."""
        routes = [getattr(route, "path", "") for route in app.routes]
        assert any("/api/symbols" in route for route in routes)

    def test_files_router_registered(self, app: FastAPI) -> None:
        """App should have files router registered."""
        routes = [getattr(route, "path", "") for route in app.routes]
        assert any("/api/files" in route for route in routes)

    def test_commits_router_registered(self, app: FastAPI) -> None:
        """App should have commits router registered."""
        routes = [getattr(route, "path", "") for route in app.routes]
        assert any("/api/commits" in route for route in routes)


class TestCorsConfiguration:
    """Tests for CORS configuration."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_cors_allows_localhost_5173(self, client: TestClient) -> None:
        """CORS should allow requests from localhost:5173 (Vite dev server)."""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS preflight should succeed
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_cors_allows_localhost_8000(self, client: TestClient) -> None:
        """CORS should allow requests from localhost:8000 (production)."""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200

    def test_cors_allows_all_methods(self, client: TestClient) -> None:
        """CORS should allow all HTTP methods."""
        for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            response = client.options(
                "/api/health",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": method,
                },
            )
            assert response.status_code == 200

    def test_cors_allows_credentials(self, client: TestClient) -> None:
        """CORS should allow credentials."""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Check for allow-credentials header
        assert response.headers.get("access-control-allow-credentials") == "true"

"""Tests for the URL builder utility."""

from src.urls import build_browse_url


class TestBuildBrowseUrl:
    def test_basic_url(self) -> None:
        url = build_browse_url("http://localhost:5173", "my-repo", "src/main.py")
        assert url == "http://localhost:5173/browse/my-repo/src/main.py"

    def test_with_line(self) -> None:
        url = build_browse_url(
            "http://localhost:5173", "my-repo", "src/main.py", line=42
        )
        assert url == "http://localhost:5173/browse/my-repo/src/main.py?line=42"

    def test_with_branch(self) -> None:
        url = build_browse_url(
            "http://localhost:5173", "my-repo", "src/main.py", branch="develop"
        )
        assert url == "http://localhost:5173/browse/my-repo/src/main.py?branch=develop"

    def test_with_commit(self) -> None:
        url = build_browse_url(
            "http://localhost:5173", "my-repo", "src/main.py", commit="abc123"
        )
        assert url == "http://localhost:5173/browse/my-repo/src/main.py?commit=abc123"

    def test_with_all_params(self) -> None:
        url = build_browse_url(
            "http://localhost:5173",
            "my-repo",
            "src/main.py",
            line=10,
            branch="main",
            commit="abc123",
        )
        assert "line=10" in url
        assert "branch=main" in url
        assert "commit=abc123" in url
        assert url.startswith("http://localhost:5173/browse/my-repo/src/main.py?")

    def test_trailing_slash_stripped(self) -> None:
        url = build_browse_url("http://localhost:5173/", "my-repo", "src/main.py")
        assert url == "http://localhost:5173/browse/my-repo/src/main.py"

    def test_path_with_special_chars(self) -> None:
        url = build_browse_url("http://localhost:5173", "my-repo", "src/hello world.py")
        assert "hello%20world" in url

    def test_repo_name_with_special_chars(self) -> None:
        url = build_browse_url("http://localhost:5173", "my repo", "src/main.py")
        assert "my%20repo" in url

"""Tests for shared API validation functions."""

import pytest
from fastapi import HTTPException

from inxr2.adapters.api.validation import validate_path, validate_repo_name


class TestValidatePath:
    """Tests for validate_path function."""

    def test_valid_simple_path(self) -> None:
        """Test a simple valid file path."""
        result = validate_path("src/main.py")
        assert result == "src/main.py"

    def test_valid_nested_path(self) -> None:
        """Test a deeply nested valid file path."""
        result = validate_path("src/components/ui/Button.tsx")
        assert result == "src/components/ui/Button.tsx"

    def test_valid_single_file(self) -> None:
        """Test a single filename without directory."""
        result = validate_path("README.md")
        assert result == "README.md"

    def test_empty_path_raises(self) -> None:
        """Test that empty path raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_path("")
        assert exc_info.value.status_code == 400
        assert "cannot be empty" in exc_info.value.detail

    def test_whitespace_path_raises(self) -> None:
        """Test that whitespace-only path raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_path("   ")
        assert exc_info.value.status_code == 400
        assert "cannot be empty" in exc_info.value.detail

    def test_absolute_path_forward_slash_raises(self) -> None:
        """Test that absolute paths with forward slash raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_path("/etc/passwd")
        assert exc_info.value.status_code == 400
        assert "Absolute paths" in exc_info.value.detail

    def test_absolute_path_backslash_raises(self) -> None:
        """Test that absolute paths with backslash raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_path("\\Windows\\System32")
        assert exc_info.value.status_code == 400
        assert "Absolute paths" in exc_info.value.detail

    def test_path_traversal_raises(self) -> None:
        """Test that path traversal attempts raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_path("../../../etc/passwd")
        assert exc_info.value.status_code == 400
        assert "Path traversal" in exc_info.value.detail

    def test_path_traversal_in_middle_raises(self) -> None:
        """Test that path traversal in middle of path raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_path("src/../../../etc/passwd")
        assert exc_info.value.status_code == 400
        assert "Path traversal" in exc_info.value.detail

    def test_path_with_dots_in_filename_allowed(self) -> None:
        """Test that dots in filenames are allowed."""
        result = validate_path("src/config.dev.json")
        assert result == "src/config.dev.json"

    def test_path_with_hidden_file_allowed(self) -> None:
        """Test that hidden files (starting with dot) are allowed."""
        result = validate_path(".gitignore")
        assert result == ".gitignore"

    def test_path_with_hidden_directory_allowed(self) -> None:
        """Test that hidden directories are allowed."""
        result = validate_path(".github/workflows/ci.yml")
        assert result == ".github/workflows/ci.yml"


class TestValidateRepoName:
    """Tests for validate_repo_name function."""

    def test_valid_simple_name(self) -> None:
        """Test a simple valid repository name."""
        result = validate_repo_name("myrepo")
        assert result == "myrepo"

    def test_valid_name_with_hyphen(self) -> None:
        """Test a valid name with hyphens."""
        result = validate_repo_name("my-awesome-repo")
        assert result == "my-awesome-repo"

    def test_valid_name_with_underscore(self) -> None:
        """Test a valid name with underscores."""
        result = validate_repo_name("my_repo_name")
        assert result == "my_repo_name"

    def test_valid_name_with_numbers(self) -> None:
        """Test a valid name with numbers."""
        result = validate_repo_name("repo123")
        assert result == "repo123"

    def test_valid_name_with_dot_in_middle(self) -> None:
        """Test a valid name with dot in the middle."""
        result = validate_repo_name("my.repo")
        assert result == "my.repo"

    def test_empty_name_raises(self) -> None:
        """Test that empty name raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_repo_name("")
        assert exc_info.value.status_code == 400
        assert "cannot be empty" in exc_info.value.detail

    def test_whitespace_name_raises(self) -> None:
        """Test that whitespace-only name raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_repo_name("   ")
        assert exc_info.value.status_code == 400
        assert "cannot be empty" in exc_info.value.detail

    def test_name_with_slash_raises(self) -> None:
        """Test that names with slashes raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_repo_name("user/repo")
        assert exc_info.value.status_code == 400
        assert "must contain only" in exc_info.value.detail

    def test_name_with_space_raises(self) -> None:
        """Test that names with spaces raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_repo_name("my repo")
        assert exc_info.value.status_code == 400
        assert "must contain only" in exc_info.value.detail

    def test_single_dot_raises(self) -> None:
        """Test that single dot raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_repo_name(".")
        assert exc_info.value.status_code == 400
        assert "cannot be '.'" in exc_info.value.detail

    def test_double_dot_raises(self) -> None:
        """Test that double dot raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_repo_name("..")
        assert exc_info.value.status_code == 400
        assert "cannot be '.'" in exc_info.value.detail

    def test_name_starting_with_dot_raises(self) -> None:
        """Test that names starting with dot raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_repo_name(".hidden")
        assert exc_info.value.status_code == 400
        assert "start/end with a dot" in exc_info.value.detail

    def test_name_ending_with_dot_raises(self) -> None:
        """Test that names ending with dot raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_repo_name("repo.")
        assert exc_info.value.status_code == 400
        assert "start/end with a dot" in exc_info.value.detail

    def test_name_with_special_chars_raises(self) -> None:
        """Test that names with special characters raise HTTPException."""
        for char in ["@", "#", "$", "%", "^", "&", "*", "(", ")", "!", "+"]:
            with pytest.raises(HTTPException) as exc_info:
                validate_repo_name(f"repo{char}name")
            assert exc_info.value.status_code == 400
            assert "must contain only" in exc_info.value.detail

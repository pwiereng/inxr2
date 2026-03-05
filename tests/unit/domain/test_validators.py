"""Tests for domain-level validators."""

import pytest

from inxr2.domain.services.validators import validate_repo_name


class TestValidateRepoName:
    """Tests for the shared repo name validator."""

    def test_valid_simple_name(self) -> None:
        validate_repo_name("myrepo")  # should not raise

    def test_valid_name_with_hyphen(self) -> None:
        validate_repo_name("my-awesome-repo")

    def test_valid_name_with_underscore(self) -> None:
        validate_repo_name("my_repo_name")

    def test_valid_name_with_numbers(self) -> None:
        validate_repo_name("repo123")

    def test_valid_name_with_dot_in_middle(self) -> None:
        validate_repo_name("my.repo")

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_repo_name("")

    def test_whitespace_name_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_repo_name("   ")

    def test_name_with_slash_raises(self) -> None:
        with pytest.raises(ValueError, match="must contain only"):
            validate_repo_name("user/repo")

    def test_name_with_space_raises(self) -> None:
        with pytest.raises(ValueError, match="must contain only"):
            validate_repo_name("my repo")

    def test_single_dot_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be '\\.'"):
            validate_repo_name(".")

    def test_double_dot_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be '\\.'"):
            validate_repo_name("..")

    def test_name_starting_with_dot_raises(self) -> None:
        with pytest.raises(ValueError, match="start/end with a dot"):
            validate_repo_name(".hidden")

    def test_name_ending_with_dot_raises(self) -> None:
        with pytest.raises(ValueError, match="start/end with a dot"):
            validate_repo_name("repo.")

    @pytest.mark.parametrize("char", ["@", "#", "$", "%", "^", "&", "*", "(", ")"])
    def test_special_characters_raise(self, char: str) -> None:
        with pytest.raises(ValueError, match="must contain only"):
            validate_repo_name(f"repo{char}name")

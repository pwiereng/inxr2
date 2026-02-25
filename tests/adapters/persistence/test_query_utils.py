"""Tests for build_text_match_filter utility."""

import pytest
from sqlalchemy import Column, ColumnElement, MetaData, String, Table

from inxr2.adapters.persistence.repositories.query_utils import (
    build_text_match_filter,
)

_metadata = MetaData()
_table = Table("t", _metadata, Column("name", String))
_col = _table.c.name


def _compile(clause: ColumnElement[bool]) -> str:
    """Compile a SQLAlchemy clause to a SQL string with literal binds."""
    return str(clause.compile(compile_kwargs={"literal_binds": True}))


class TestBuildTextMatchFilterLike:
    """Tests for LIKE/ILIKE mode (default)."""

    def test_like_case_sensitive(self) -> None:
        sql = _compile(build_text_match_filter(_col, "hello"))
        assert "LIKE" in sql
        assert "%hello%" in sql

    def test_ilike_case_insensitive(self) -> None:
        sql = _compile(build_text_match_filter(_col, "hello", case_sensitive=False))
        # Generic dialect renders ilike as lower(col) LIKE lower(val);
        # PostgreSQL dialect renders it as ILIKE.
        assert "ILIKE" in sql or "lower(" in sql

    def test_escapes_percent(self) -> None:
        sql = _compile(build_text_match_filter(_col, "100%"))
        assert r"\%" in sql

    def test_escapes_underscore(self) -> None:
        sql = _compile(build_text_match_filter(_col, "foo_bar"))
        assert r"\_" in sql

    def test_escapes_backslash(self) -> None:
        sql = _compile(build_text_match_filter(_col, "a\\b"))
        # The input backslash is escaped to \\, wrapped in %...%
        assert "\\\\" in sql

    def test_explicit_none_mode_uses_like(self) -> None:
        sql = _compile(build_text_match_filter(_col, "x", mode=None))
        assert "LIKE" in sql


class TestBuildTextMatchFilterRegex:
    """Tests for regex mode."""

    def test_regex_case_sensitive(self) -> None:
        sql = _compile(build_text_match_filter(_col, "foo.*bar", mode="regex"))
        assert "~ " in sql or "~" in sql

    def test_regex_case_insensitive(self) -> None:
        sql = _compile(
            build_text_match_filter(_col, "foo", mode="regex", case_sensitive=False)
        )
        assert "~*" in sql

    def test_word_boundary_translation(self) -> None:
        sql = _compile(build_text_match_filter(_col, r"\bfoo\b", mode="regex"))
        assert r"\y" in sql

    def test_invalid_pattern_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid regex"):
            build_text_match_filter(_col, "[invalid", mode="regex")

    def test_dangerous_pattern_raises(self) -> None:
        with pytest.raises(ValueError, match="dangerous"):
            build_text_match_filter(_col, "(.*)+", mode="regex")

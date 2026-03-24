"""Shared query utilities for text matching and extension filtering."""

from typing import cast

from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute

from .regex_utils import translate_word_boundaries, validate_regex_pattern

NONE_SENTINEL = "(none)"

# Cross-language kind aliases: querying a key also matches all values.
# e.g. kind="interface" returns both interface and protocol symbols (Swift).
KIND_ALIASES: dict[str, list[str]] = {
    "interface": ["interface", "protocol"],
}


def split_extension_filter(extensions: list[str]) -> tuple[list[str], bool]:
    """Split extension list into real extensions and a flag for extensionless files.

    Returns (real_extensions, has_none) where has_none indicates the "(none)"
    sentinel was present (meaning include files with no extension).
    """
    real_exts = [e for e in extensions if e != NONE_SENTINEL]
    has_none = NONE_SENTINEL in extensions
    return real_exts, has_none


# Accept both ORM attributes (Model.column) and core column elements.
_Column = ColumnElement[str] | InstrumentedAttribute[str]


def build_text_match_filter(
    col: _Column,
    text: str,
    mode: str | None = None,
    case_sensitive: bool = True,
) -> ColumnElement[bool]:
    """Build a WHERE clause for text matching (regex or LIKE).

    Args:
        col: SQLAlchemy column or attribute to match against.
        text: The search text or regex pattern.
        mode: ``"regex"`` for regex matching, otherwise LIKE/ILIKE.
        case_sensitive: Whether the match is case-sensitive.

    Returns:
        A SQLAlchemy expression suitable for ``.where()``.
    """
    # InstrumentedAttribute proxies all ColumnElement operations at runtime,
    # but the stubs don't expose .like()/.ilike()/.op() on it directly.
    c = cast(ColumnElement[str], col)

    if mode == "regex":
        validate_regex_pattern(text)
        pg_pattern = translate_word_boundaries(text)
        op = "~" if case_sensitive else "~*"
        return c.op(op)(pg_pattern)

    escaped = text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    if case_sensitive:
        return c.like(f"%{escaped}%", escape="\\")
    return c.ilike(f"%{escaped}%", escape="\\")

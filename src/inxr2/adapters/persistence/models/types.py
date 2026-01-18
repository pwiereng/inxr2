"""Custom SQLAlchemy types for cross-database compatibility."""

from typing import Any, cast

from sqlalchemy import JSON, String, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY


class StringArray(TypeDecorator):
    """
    A string array type that works with both PostgreSQL and SQLite.

    - PostgreSQL: Uses native ARRAY(String) type
    - SQLite: Uses JSON type and converts list to/from JSON
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        """Load the appropriate type for the current dialect."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(String))
        else:
            return dialect.type_descriptor(JSON)

    def process_bind_param(self, value: list[str] | None, dialect: Any) -> Any:
        """Convert Python list to database format."""
        if value is None:
            return None
        if dialect.name == "postgresql":
            # PostgreSQL handles list natively
            return value
        else:
            # SQLite needs JSON serialization (happens automatically)
            return value

    def process_result_value(self, value: Any, dialect: Any) -> list[str] | None:
        """Convert database value to Python list."""
        if value is None:
            return None
        # Both PostgreSQL and SQLite return the value in the correct format
        return cast(list[str], value)

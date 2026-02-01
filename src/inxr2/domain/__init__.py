"""
Domain Layer - Layer 1 (Innermost)

Pure business logic with zero external dependencies.
Contains entities, value objects, domain exceptions, and domain services.

Dependency Rule: This layer has NO dependencies on any other layer.
"""

from .constants import (
    DEFAULT_INDEXING_LANGUAGES,
    SUPPORTED_LANGUAGES_WITH_PARSERS,
)

__all__ = [
    "DEFAULT_INDEXING_LANGUAGES",
    "SUPPORTED_LANGUAGES_WITH_PARSERS",
]

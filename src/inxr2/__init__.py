"""
INXR2 - Cross-reference code browser for git repositories.

A modern code browser designed specifically for git-based workflows,
providing semantic code navigation, temporal browsing, and cross-repository
search capabilities.

Architecture: Clean Architecture (Hexagonal/Ports & Adapters)
- Domain: Pure business logic (entities, value objects, exceptions)
- Application: Use cases and ports (interfaces)
- Adapters: Interface adapters (API, CLI, persistence, external services)
- Infrastructure: Frameworks and drivers (FastAPI, SQLAlchemy, etc)
"""

__version__ = "0.1.0"

# TODO: Export key domain entities for convenience
# from .domain.entities import Repository, Commit, File, Symbol, Reference
# from .domain.value_objects import SymbolLocation, CommitHash, SymbolKind

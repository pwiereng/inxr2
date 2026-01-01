"""Repository port interfaces - data access abstractions."""

from abc import ABC, abstractmethod

from ...domain.entities import File, Symbol


class SymbolRepositoryPort(ABC):
    """
    Port for symbol repository operations.

    Implementations will use specific persistence mechanisms (PostgreSQL, etc).

    TODO: Add query methods (search, filter, etc)
    TODO: Add bulk operations
    TODO: Add transaction support
    """

    @abstractmethod
    async def save(self, symbol: Symbol) -> Symbol:
        """
        Save a symbol.

        Args:
            symbol: Symbol to save

        Returns:
            Saved symbol with generated ID (if new)

        TODO: Implement in adapter layer
        """
        pass

    @abstractmethod
    async def find_by_id(self, symbol_id: str) -> Symbol | None:
        """
        Find symbol by ID.

        Args:
            symbol_id: Symbol identifier

        Returns:
            Symbol if found, None otherwise

        TODO: Implement in adapter layer
        """
        pass

    @abstractmethod
    async def find_by_name(
        self, name: str, repository_id: str | None = None
    ) -> list[Symbol]:
        """
        Find symbols by name.

        Args:
            name: Symbol name to search for
            repository_id: Optional repository filter

        Returns:
            List of matching symbols

        TODO: Implement in adapter layer
        TODO: Add pagination support
        """
        pass


class FileRepositoryPort(ABC):
    """
    Port for file repository operations.

    TODO: Add query methods
    TODO: Add bulk operations
    """

    @abstractmethod
    async def save(self, file: File) -> File:
        """
        Save a file.

        Args:
            file: File to save

        Returns:
            Saved file with generated ID (if new)

        TODO: Implement in adapter layer
        """
        pass

    @abstractmethod
    async def find_by_id(self, file_id: str) -> File | None:
        """
        Find file by ID.

        Args:
            file_id: File identifier

        Returns:
            File if found, None otherwise

        TODO: Implement in adapter layer
        """
        pass

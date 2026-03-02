"""Mappers to convert between domain entities and ORM models.

Clean Architecture requires separation between domain entities and persistence models.
These mappers handle the conversion in both directions.
"""

from datetime import UTC, datetime

from ...domain.entities import (
    Commit,
    File,
    IndexStatus,
    Reference,
    Repository,
    Symbol,
    TextContent,
)
from ...domain.value_objects import CommitHash, ReferenceType, SymbolKind
from .models import (
    CommitModel,
    FileModel,
    IndexStatusModel,
    ReferenceModel,
    RepositoryModel,
    SymbolModel,
    TextContentModel,
)


class RepositoryMapper:
    """Maps between Repository entity and RepositoryModel."""

    @staticmethod
    def to_domain(model: RepositoryModel) -> Repository:
        """Convert ORM model to domain entity."""
        return Repository(
            id=model.id,
            name=model.name,
            url=model.url,
            description=model.description,
            default_branch=model.default_branch,
            config=model.config,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(entity: Repository) -> RepositoryModel:
        """Convert domain entity to ORM model."""
        return RepositoryModel(
            id=entity.id,
            name=entity.name,
            url=entity.url,
            description=entity.description,
            default_branch=entity.default_branch,
            config=entity.config,
            created_at=entity.created_at or datetime.now(UTC).replace(tzinfo=None),
            updated_at=entity.updated_at or datetime.now(UTC).replace(tzinfo=None),
        )


class CommitMapper:
    """Maps between Commit entity and CommitModel.

    Design note: Only essential data is stored in DB. Author info, message,
    and parent hashes are queried from git on-demand. See ARCHITECTURAL_REVIEW.md.
    """

    @staticmethod
    def to_domain(model: CommitModel) -> Commit:
        """Convert ORM model to domain entity."""
        return Commit(
            id=model.id,
            repository_id=model.repository_id,
            commit_hash=CommitHash(value=model.commit_hash),
            author_date=model.author_date,
            commit_date=model.commit_date,
            indexed_at=model.indexed_at,
        )

    @staticmethod
    def to_model(entity: Commit) -> CommitModel:
        """Convert domain entity to ORM model."""
        return CommitModel(
            id=entity.id,
            repository_id=entity.repository_id,
            commit_hash=entity.commit_hash.value,
            author_date=entity.author_date,
            commit_date=entity.commit_date,
            indexed_at=entity.indexed_at or datetime.now(UTC).replace(tzinfo=None),
        )


class FileMapper:
    """Maps between File entity and FileModel."""

    @staticmethod
    def to_domain(model: FileModel) -> File:
        """Convert ORM model to domain entity."""
        return File(
            id=model.id,
            repository_id=model.repository_id,
            path=model.path,
            content_hash=model.content_hash,
            size_bytes=model.size_bytes,
            language=model.language,
            extension=model.extension,
            encoding=model.encoding,
            is_binary=model.is_binary,
            line_count=model.line_count,
            indexed_at=model.indexed_at,
        )

    @staticmethod
    def to_model(entity: File) -> FileModel:
        """Convert domain entity to ORM model."""
        return FileModel(
            id=entity.id,
            repository_id=entity.repository_id,
            path=entity.path,
            content_hash=entity.content_hash,
            size_bytes=entity.size_bytes,
            language=entity.language,
            extension=entity.extension,
            encoding=entity.encoding,
            is_binary=entity.is_binary,
            line_count=entity.line_count,
            indexed_at=entity.indexed_at or datetime.now(UTC).replace(tzinfo=None),
        )


class SymbolMapper:
    """Maps between Symbol entity and SymbolModel."""

    @staticmethod
    def to_domain(model: SymbolModel) -> Symbol:
        """Convert ORM model to domain entity."""
        return Symbol(
            id=model.id,
            file_id=model.file_id,
            repository_id=model.repository_id,
            name=model.name,
            kind=SymbolKind(model.kind),
            start_line=model.start_line,
            start_column=model.start_column,
            end_line=model.end_line,
            end_column=model.end_column,
            qualified_name=model.qualified_name,
            parent_symbol_id=model.parent_symbol_id,
            scope=model.scope,
            signature=model.signature,
            docstring=model.docstring,
            metadata=model.extra_metadata,
            indexed_at=model.indexed_at,
        )

    @staticmethod
    def to_model(entity: Symbol) -> SymbolModel:
        """Convert domain entity to ORM model."""
        return SymbolModel(
            id=entity.id,
            file_id=entity.file_id,
            repository_id=entity.repository_id,
            name=entity.name,
            kind=entity.kind.value,
            start_line=entity.start_line,
            start_column=entity.start_column,
            end_line=entity.end_line,
            end_column=entity.end_column,
            qualified_name=entity.qualified_name,
            parent_symbol_id=entity.parent_symbol_id,
            scope=entity.scope,
            signature=entity.signature,
            docstring=entity.docstring,
            extra_metadata=entity.metadata,
            indexed_at=entity.indexed_at or datetime.now(UTC).replace(tzinfo=None),
        )


class ReferenceMapper:
    """Maps between Reference entity and ReferenceModel."""

    @staticmethod
    def to_domain(model: ReferenceModel) -> Reference:
        """Convert ORM model to domain entity."""
        return Reference(
            id=model.id,
            repository_id=model.repository_id,
            source_file_id=model.source_file_id,
            source_line=model.source_line,
            source_column=model.source_column,
            source_end_column=model.source_end_column,
            reference_text=model.reference_text,
            reference_type=ReferenceType(model.reference_type),
            target_symbol_id=model.target_symbol_id,
            target_repository_id=model.target_repository_id,
            is_definition=model.is_definition,
            is_write=model.is_write,
            resolution_confidence=model.resolution_confidence,
            metadata=model.extra_metadata,
            indexed_at=model.indexed_at,
        )

    @staticmethod
    def to_model(entity: Reference) -> ReferenceModel:
        """Convert domain entity to ORM model."""
        return ReferenceModel(
            id=entity.id,
            repository_id=entity.repository_id,
            source_file_id=entity.source_file_id,
            source_line=entity.source_line,
            source_column=entity.source_column,
            source_end_column=entity.source_end_column,
            reference_text=entity.reference_text,
            reference_type=entity.reference_type.value,
            target_symbol_id=entity.target_symbol_id,
            target_repository_id=entity.target_repository_id,
            is_definition=entity.is_definition,
            is_write=entity.is_write,
            resolution_confidence=entity.resolution_confidence,
            extra_metadata=entity.metadata,
            indexed_at=entity.indexed_at or datetime.now(UTC).replace(tzinfo=None),
        )


class IndexStatusMapper:
    """Maps between IndexStatus entity and IndexStatusModel."""

    @staticmethod
    def to_domain(model: IndexStatusModel) -> IndexStatus:
        """Convert ORM model to domain entity."""
        return IndexStatus(
            id=model.id,
            repository_id=model.repository_id,
            branch=model.branch,
            indexing_status=model.indexing_status,
            last_indexed_commit=model.last_indexed_commit,
            oldest_indexed_commit=model.oldest_indexed_commit,
            last_indexed_at=model.last_indexed_at,
            indexing_started_at=model.indexing_started_at,
            total_commits_indexed=model.total_commits_indexed,
            total_files_indexed=model.total_files_indexed,
            total_symbols_indexed=model.total_symbols_indexed,
            total_references_indexed=model.total_references_indexed,
            last_indexing_duration_seconds=model.last_indexing_duration_seconds,
            last_resolving_duration_seconds=model.last_resolving_duration_seconds,
            error_message=model.error_message,
            error_count=model.error_count,
            indexer_version=model.indexer_version,
            metadata=model.extra_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(entity: IndexStatus) -> IndexStatusModel:
        """Convert domain entity to ORM model."""
        return IndexStatusModel(
            id=entity.id,
            repository_id=entity.repository_id,
            branch=entity.branch,
            indexing_status=entity.indexing_status,
            last_indexed_commit=entity.last_indexed_commit,
            oldest_indexed_commit=entity.oldest_indexed_commit,
            last_indexed_at=entity.last_indexed_at,
            indexing_started_at=entity.indexing_started_at,
            total_commits_indexed=entity.total_commits_indexed,
            total_files_indexed=entity.total_files_indexed,
            total_symbols_indexed=entity.total_symbols_indexed,
            total_references_indexed=entity.total_references_indexed,
            last_indexing_duration_seconds=entity.last_indexing_duration_seconds,
            last_resolving_duration_seconds=entity.last_resolving_duration_seconds,
            error_message=entity.error_message,
            error_count=entity.error_count,
            indexer_version=entity.indexer_version,
            extra_metadata=entity.metadata,
            created_at=entity.created_at or datetime.now(UTC).replace(tzinfo=None),
            updated_at=entity.updated_at or datetime.now(UTC).replace(tzinfo=None),
        )


class TextContentMapper:
    """Maps between TextContent entity and TextContentModel."""

    @staticmethod
    def to_domain(model: TextContentModel) -> TextContent:
        """Convert ORM model to domain entity."""
        return TextContent(
            id=model.id,
            repository_id=model.repository_id,
            commit_id=model.commit_id,
            source_type=model.source_type,
            source_file_id=model.source_file_id,
            source_line=model.source_line,
            source_end_line=model.source_end_line,
            content=model.content,
            language=model.language,
            content_type=model.content_type,
            indexed_at=model.indexed_at,
        )

    @staticmethod
    def to_model(entity: TextContent) -> TextContentModel:
        """Convert domain entity to ORM model."""
        return TextContentModel(
            id=entity.id,
            repository_id=entity.repository_id,
            commit_id=entity.commit_id,
            source_type=entity.source_type,
            source_file_id=entity.source_file_id,
            source_line=entity.source_line,
            source_end_line=entity.source_end_line,
            content=entity.content,
            language=entity.language,
            content_type=entity.content_type,
            indexed_at=entity.indexed_at or datetime.now(UTC).replace(tzinfo=None),
        )

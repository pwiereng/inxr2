"""PostgreSQL reference repository adapter."""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import ReferenceRepositoryPort
from ....domain.entities import Reference
from ..mappers import ReferenceMapper
from ..models.file import FileModel
from ..models.reference import ReferenceModel


class PostgresReferenceRepository(ReferenceRepositoryPort):
    """PostgreSQL implementation of ReferenceRepositoryPort."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.mapper = ReferenceMapper()

    async def save(self, reference: Reference) -> Reference:
        """Save or update a reference."""
        model = self.mapper.to_model(reference)

        if reference.id is None:
            self.session.add(model)
        else:
            model = await self.session.merge(model)

        await self.session.flush()
        await self.session.refresh(model)

        return self.mapper.to_domain(model)

    async def save_many(self, references: list[Reference]) -> list[Reference]:
        """Bulk save references for performance."""
        if not references:
            return []

        models = [self.mapper.to_model(ref) for ref in references]
        self.session.add_all(models)
        await self.session.flush()

        for model in models:
            await self.session.refresh(model)

        return [self.mapper.to_domain(model) for model in models]

    async def find_by_id(self, reference_id: int) -> Reference | None:
        """Find reference by ID."""
        result = await self.session.execute(
            select(ReferenceModel).where(ReferenceModel.id == reference_id)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def find_references_to_symbol(
        self, symbol_id: int, limit: int = 100, commit_id: int | None = None
    ) -> list[Reference]:
        """Find all references TO a symbol (find usages).

        Args:
            symbol_id: The target symbol ID
            limit: Maximum number of results
            commit_id: Filter by specific commit for time travel (optional).
                       If None, returns from latest version of each file.
        """
        if commit_id is not None:
            # Time travel mode: filter by specific commit
            result = await self.session.execute(
                select(ReferenceModel)
                .join(FileModel, ReferenceModel.source_file_id == FileModel.id)
                .where(
                    ReferenceModel.target_symbol_id == symbol_id,
                    FileModel.commit_id == commit_id,
                )
                .order_by(ReferenceModel.source_line)
                .limit(limit)
            )
            models = result.scalars().all()
            return [self.mapper.to_domain(model) for model in models]

        # Default: get from latest version of each file
        # First get the repository_id from any reference to this symbol
        ref_check = await self.session.execute(
            select(ReferenceModel.repository_id)
            .where(ReferenceModel.target_symbol_id == symbol_id)
            .limit(1)
        )
        repo_id_result = ref_check.scalar_one_or_none()
        if repo_id_result is None:
            return []

        # Subquery to find the latest file ID for each path
        latest_files = (
            select(func.max(FileModel.id).label("latest_id"))
            .where(FileModel.repository_id == repo_id_result)
            .group_by(FileModel.path)
            .subquery()
        )

        result = await self.session.execute(
            select(ReferenceModel)
            .where(
                ReferenceModel.target_symbol_id == symbol_id,
                ReferenceModel.source_file_id.in_(select(latest_files.c.latest_id)),
            )
            .order_by(ReferenceModel.source_line)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def find_references_by_text(
        self,
        text: str,
        repository_id: int,
        limit: int = 100,
        commit_id: int | None = None,
    ) -> list[Reference]:
        """Find all references matching the given text.

        Useful for finding all calls to a symbol name when multiple
        symbols share the same name (e.g., save() methods in different classes).

        Args:
            text: The reference text to match
            repository_id: Filter by repository
            limit: Maximum number of results
            commit_id: Filter by specific commit for time travel (optional).
                       If None, returns from latest version of each file.
        """
        if commit_id is not None:
            # Time travel mode: filter by specific commit
            result = await self.session.execute(
                select(ReferenceModel)
                .join(FileModel, ReferenceModel.source_file_id == FileModel.id)
                .where(
                    ReferenceModel.reference_text == text,
                    ReferenceModel.repository_id == repository_id,
                    FileModel.commit_id == commit_id,
                )
                .order_by(ReferenceModel.source_file_id, ReferenceModel.source_line)
                .limit(limit)
            )
            models = result.scalars().all()
            return [self.mapper.to_domain(model) for model in models]

        # Default: get from latest version of each file
        # Subquery to find the latest file ID for each path in the repository
        # (Since file IDs are auto-incrementing, max ID = latest version)
        latest_files = (
            select(func.max(FileModel.id).label("latest_id"))
            .where(FileModel.repository_id == repository_id)
            .group_by(FileModel.path)
            .subquery()
        )

        result = await self.session.execute(
            select(ReferenceModel)
            .where(
                ReferenceModel.reference_text == text,
                ReferenceModel.repository_id == repository_id,
                ReferenceModel.source_file_id.in_(select(latest_files.c.latest_id)),
            )
            .order_by(ReferenceModel.source_file_id, ReferenceModel.source_line)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def list_by_file(self, file_id: int) -> list[Reference]:
        """List all references in a file."""
        result = await self.session.execute(
            select(ReferenceModel)
            .where(ReferenceModel.source_file_id == file_id)
            .order_by(ReferenceModel.source_line, ReferenceModel.source_column)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def delete_by_file(self, file_id: int) -> int:
        """Delete all references for a file (for re-indexing). Returns count deleted."""
        result = await self.session.execute(
            delete(ReferenceModel).where(ReferenceModel.source_file_id == file_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def count_by_repository(self, repository_id: int) -> int:
        """Count references for a repository."""
        result = await self.session.execute(
            select(func.count(ReferenceModel.id)).where(
                ReferenceModel.repository_id == repository_id
            )
        )
        return result.scalar() or 0

    async def delete_by_repository(self, repository_id: int) -> int:
        """Delete all references for a repository. Returns count deleted."""
        result = await self.session.execute(
            delete(ReferenceModel).where(ReferenceModel.repository_id == repository_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def count_unresolved_references(self, repository_id: int) -> int:
        """Count references that don't have a target_symbol_id set."""
        result = await self.session.execute(
            select(func.count(ReferenceModel.id)).where(
                ReferenceModel.repository_id == repository_id,
                ReferenceModel.target_symbol_id.is_(None),
            )
        )
        return result.scalar() or 0

    async def resolve_references_batch(
        self,
        repository_id: int,
        batch_size: int = 1000,
        commit_aware: bool = False,
    ) -> int:
        """Resolve a batch of unlinked references.

        Uses a subquery to limit the update to batch_size references at a time.

        Resolution priority (deterministic):
        1. Same file - most likely the correct local symbol
        2. Same language - cross-file but same language preferred
        3. Symbol ID - deterministic tiebreaker for consistency

        This ensures clicking on a reference always goes to the same symbol,
        rather than an arbitrary one when multiple symbols share the same name.
        """
        if commit_aware:
            # Time travel mode: only match references to symbols from same commit
            # Uses correlated subquery to pick best match per reference
            result = await self.session.execute(
                text("""
                    UPDATE "references" r
                    SET target_symbol_id = (
                        SELECT s.id
                        FROM symbols s
                        JOIN files sf ON s.file_id = sf.id
                        JOIN files rf ON r.source_file_id = rf.id
                        WHERE s.name = r.reference_text
                          AND s.repository_id = r.repository_id
                          AND s.commit_id = r.commit_id
                        ORDER BY
                            (s.file_id = r.source_file_id) DESC,
                            (sf.language = rf.language) DESC,
                            s.id
                        LIMIT 1
                    )
                    WHERE r.id IN (
                        SELECT r2.id FROM "references" r2
                        JOIN symbols s2 ON r2.reference_text = s2.name
                            AND r2.repository_id = s2.repository_id
                            AND r2.commit_id = s2.commit_id
                        WHERE r2.repository_id = :repo_id
                          AND r2.target_symbol_id IS NULL
                        LIMIT :batch_size
                    )
                """),
                {"repo_id": repository_id, "batch_size": batch_size},
            )
        else:
            # Cross-commit mode: match references to any symbol in repository
            # Uses correlated subquery to pick best match per reference
            result = await self.session.execute(
                text("""
                    UPDATE "references" r
                    SET target_symbol_id = (
                        SELECT s.id
                        FROM symbols s
                        JOIN files sf ON s.file_id = sf.id
                        JOIN files rf ON r.source_file_id = rf.id
                        WHERE s.name = r.reference_text
                          AND s.repository_id = r.repository_id
                        ORDER BY
                            (s.file_id = r.source_file_id) DESC,
                            (sf.language = rf.language) DESC,
                            s.id
                        LIMIT 1
                    )
                    WHERE r.id IN (
                        SELECT r2.id FROM "references" r2
                        JOIN symbols s2 ON r2.reference_text = s2.name
                            AND r2.repository_id = s2.repository_id
                        WHERE r2.repository_id = :repo_id
                          AND r2.target_symbol_id IS NULL
                        LIMIT :batch_size
                    )
                """),
                {"repo_id": repository_id, "batch_size": batch_size},
            )

        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def resolve_unlinked_references(
        self, repository_id: int, commit_aware: bool = False
    ) -> int:
        """Resolve references to their target symbols.

        After indexing, this method matches reference_text to symbol names
        and updates the target_symbol_id for each reference.

        Args:
            repository_id: The repository ID to resolve references for
            commit_aware: If True, only match references to symbols from the
                         same commit (for time travel consistency). If False,
                         match across all commits in the repository.

        Returns:
            Number of references resolved
        """
        if commit_aware:
            # Time travel mode: only match references to symbols from same commit
            result = await self.session.execute(
                text("""
                    UPDATE "references" r
                    SET target_symbol_id = s.id
                    FROM symbols s
                    WHERE r.repository_id = :repo_id
                      AND s.repository_id = :repo_id
                      AND r.commit_id = s.commit_id
                      AND r.reference_text = s.name
                      AND r.target_symbol_id IS NULL
                """),
                {"repo_id": repository_id},
            )
        else:
            # Cross-commit mode: match references to any symbol in repository
            result = await self.session.execute(
                text("""
                    UPDATE "references" r
                    SET target_symbol_id = s.id
                    FROM symbols s
                    WHERE r.repository_id = :repo_id
                      AND s.repository_id = :repo_id
                      AND r.reference_text = s.name
                      AND r.target_symbol_id IS NULL
                """),
                {"repo_id": repository_id},
            )

        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def copy_references_to_file(
        self,
        source_file_id: int,
        target_file_id: int,
        target_commit_id: int,
        target_repository_id: int,
    ) -> int:
        """Copy all references from source file to target file.

        Creates new reference records with the target file/commit IDs while
        preserving all other reference attributes. target_symbol_id is set to
        NULL and will be resolved later by resolve_unlinked_references.
        """
        # Fetch source references
        result = await self.session.execute(
            select(ReferenceModel).where(
                ReferenceModel.source_file_id == source_file_id
            )
        )
        source_refs = list(result.scalars().all())

        if not source_refs:
            return 0

        # Create new references with updated file/commit/repository IDs
        now = datetime.now(UTC).replace(tzinfo=None)
        new_refs = [
            ReferenceModel(
                repository_id=target_repository_id,
                commit_id=target_commit_id,
                source_file_id=target_file_id,
                source_line=ref.source_line,
                source_column=ref.source_column,
                source_end_column=ref.source_end_column,
                reference_text=ref.reference_text,
                reference_type=ref.reference_type,
                is_definition=ref.is_definition,
                is_write=ref.is_write,
                resolution_confidence=ref.resolution_confidence,
                extra_metadata=ref.extra_metadata,
                # target_symbol_id set to NULL for later resolution
                target_symbol_id=None,
                target_repository_id=None,
                # Explicitly set indexed_at for SQLite compatibility in tests
                indexed_at=now,
            )
            for ref in source_refs
        ]

        self.session.add_all(new_refs)
        await self.session.flush()
        return len(new_refs)

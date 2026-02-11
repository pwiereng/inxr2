"""PostgreSQL reference repository adapter."""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import ReferenceRepositoryPort
from ....domain.entities import Reference
from ..mappers import ReferenceMapper
from ..models.branch_commit import BranchCommitModel
from ..models.file import FileModel
from ..models.reference import ReferenceModel
from ._latest_file_query import latest_file_ids_subquery


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
        self,
        symbol_id: int,
        limit: int = 100,
        commit_id: int | None = None,
        branch: str | None = None,
    ) -> list[Reference]:
        """Find all references TO a symbol (find usages).

        Args:
            symbol_id: The target symbol ID
            limit: Maximum number of results
            commit_id: Filter by specific commit for time travel (optional).
                       If None, returns from latest version of each file.
            branch: Filter by branch name (only show refs from files on this branch).
        """
        if commit_id is not None:
            # Time travel mode: filter by specific commit
            query = (
                select(ReferenceModel)
                .join(FileModel, ReferenceModel.source_file_id == FileModel.id)
                .where(
                    ReferenceModel.target_symbol_id == symbol_id,
                    FileModel.commit_id == commit_id,
                )
            )
            # Add branch filter if specified
            if branch is not None:
                query = query.join(
                    BranchCommitModel,
                    (BranchCommitModel.commit_id == FileModel.commit_id)
                    & (BranchCommitModel.repository_id == FileModel.repository_id),
                ).where(BranchCommitModel.branch == branch)

            result = await self.session.execute(
                query.order_by(ReferenceModel.source_line).limit(limit)
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

        latest_files_q = latest_file_ids_subquery(repo_id_result, branch=branch)

        result = await self.session.execute(
            select(ReferenceModel)
            .where(
                ReferenceModel.target_symbol_id == symbol_id,
                ReferenceModel.source_file_id.in_(latest_files_q),
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
        branch: str | None = None,
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
            branch: Filter by branch name (only show refs from files on this branch).
        """
        if commit_id is not None:
            # Time travel mode: filter by specific commit
            query = (
                select(ReferenceModel)
                .join(FileModel, ReferenceModel.source_file_id == FileModel.id)
                .where(
                    ReferenceModel.reference_text == text,
                    ReferenceModel.repository_id == repository_id,
                    FileModel.commit_id == commit_id,
                )
            )
            # Add branch filter if specified
            if branch is not None:
                query = query.join(
                    BranchCommitModel,
                    (BranchCommitModel.commit_id == FileModel.commit_id)
                    & (BranchCommitModel.repository_id == FileModel.repository_id),
                ).where(BranchCommitModel.branch == branch)

            result = await self.session.execute(
                query.order_by(
                    ReferenceModel.source_file_id, ReferenceModel.source_line
                ).limit(limit)
            )
            models = result.scalars().all()
            return [self.mapper.to_domain(model) for model in models]

        latest_files_q = latest_file_ids_subquery(repository_id, branch=branch)

        result = await self.session.execute(
            select(ReferenceModel)
            .where(
                ReferenceModel.reference_text == text,
                ReferenceModel.repository_id == repository_id,
                ReferenceModel.source_file_id.in_(latest_files_q),
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

        Uses a three-pass UPDATE ... FROM with pre-computed lookup tables.
        Each lookup groups symbols by name (small result), then joins refs
        against it inside the FROM subquery. LIMIT applies after the join
        so only matchable refs are selected — unresolvable refs (builtins)
        are naturally excluded.

        Resolution priority (deterministic):
        1. Same file - most likely the correct local symbol
        2. Same language - cross-file but same language preferred
        3. Lowest symbol ID - deterministic tiebreaker for consistency

        This ensures clicking on a reference always goes to the same symbol,
        rather than an arbitrary one when multiple symbols share the same name.
        """
        # Build SQL fragments for commit-aware vs cross-commit mode.
        # Each pass has its own SELECT/GROUP BY/JOIN fragments.
        if commit_aware:
            sf_select = "s.name, s.file_id, s.commit_id"
            sf_group = "s.name, s.file_id, s.commit_id"
            sf_best_join = (
                "ON r.reference_text = best.name"
                " AND r.source_file_id = best.file_id"
                " AND r.commit_id = best.commit_id"
            )
            sl_select = "s.name, f.language, s.commit_id"
            sl_group = "s.name, f.language, s.commit_id"
            sl_best_join = (
                "ON r.reference_text = best.name"
                " AND rf.language = best.language"
                " AND r.commit_id = best.commit_id"
            )
            cf_select = "s.name, s.commit_id"
            cf_group = "s.name, s.commit_id"
            cf_best_join = (
                "ON r.reference_text = best.name" " AND r.commit_id = best.commit_id"
            )
        else:
            sf_select = "s.name, s.file_id"
            sf_group = "s.name, s.file_id"
            sf_best_join = (
                "ON r.reference_text = best.name" " AND r.source_file_id = best.file_id"
            )
            sl_select = "s.name, f.language"
            sl_group = "s.name, f.language"
            sl_best_join = (
                "ON r.reference_text = best.name" " AND rf.language = best.language"
            )
            cf_select = "s.name"
            cf_group = "s.name"
            cf_best_join = "ON r.reference_text = best.name"

        total_resolved = 0

        # Pass 1: Same-file resolution (preferred)
        # Pre-computes best symbol per (name, file_id), then joins refs
        # against it. LIMIT applies after join — only matchable refs selected.
        result = await self.session.execute(
            text(f"""
                UPDATE "references"
                SET target_symbol_id = sub.target_id
                FROM (
                    SELECT r.id AS ref_id, best.min_id AS target_id
                    FROM "references" r
                    JOIN (
                        SELECT {sf_select}, MIN(s.id) AS min_id
                        FROM symbols s
                        WHERE s.repository_id = :repo_id
                        GROUP BY {sf_group}
                    ) best {sf_best_join}
                    WHERE r.repository_id = :repo_id
                      AND r.target_symbol_id IS NULL
                    LIMIT :batch_size
                ) sub
                WHERE "references".id = sub.ref_id
            """),
            {"repo_id": repository_id, "batch_size": batch_size},
        )
        pass1_count = result.rowcount or 0  # type: ignore[attr-defined]
        total_resolved += pass1_count

        # Pass 2: Same-language cross-file resolution
        # Joins files table in the lookup to get language. Joins refs with
        # their source file to match language. Small lookup (GROUP BY name,
        # language) avoids the per-row JOIN that made the old approach slow.
        remaining = batch_size - total_resolved
        if remaining > 0:
            result = await self.session.execute(
                text(f"""
                    UPDATE "references"
                    SET target_symbol_id = sub.target_id
                    FROM (
                        SELECT r.id AS ref_id, best.min_id AS target_id
                        FROM "references" r
                        JOIN files rf ON r.source_file_id = rf.id
                        JOIN (
                            SELECT {sl_select}, MIN(s.id) AS min_id
                            FROM symbols s
                            JOIN files f ON s.file_id = f.id
                            WHERE s.repository_id = :repo_id
                            GROUP BY {sl_group}
                        ) best {sl_best_join}
                        WHERE r.repository_id = :repo_id
                          AND r.target_symbol_id IS NULL
                        LIMIT :batch_size
                    ) sub
                    WHERE "references".id = sub.ref_id
                """),
                {"repo_id": repository_id, "batch_size": remaining},
            )
            total_resolved += result.rowcount or 0  # type: ignore[attr-defined]

        # Pass 3: Any-match cross-file resolution (lowest ID fallback)
        # Pre-computes best symbol per name, then joins remaining unresolved refs.
        remaining = batch_size - total_resolved
        if remaining > 0:
            result = await self.session.execute(
                text(f"""
                    UPDATE "references"
                    SET target_symbol_id = sub.target_id
                    FROM (
                        SELECT r.id AS ref_id, best.min_id AS target_id
                        FROM "references" r
                        JOIN (
                            SELECT {cf_select}, MIN(s.id) AS min_id
                            FROM symbols s
                            WHERE s.repository_id = :repo_id
                            GROUP BY {cf_group}
                        ) best {cf_best_join}
                        WHERE r.repository_id = :repo_id
                          AND r.target_symbol_id IS NULL
                        LIMIT :batch_size
                    ) sub
                    WHERE "references".id = sub.ref_id
                """),
                {"repo_id": repository_id, "batch_size": remaining},
            )
            total_resolved += result.rowcount or 0  # type: ignore[attr-defined]

        await self.session.flush()
        return total_resolved

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
        symbol_id_mapping: dict[int, int] | None = None,
    ) -> int:
        """Copy all references from source file to target file.

        Creates new reference records with the target file/commit IDs while
        preserving all other reference attributes. When symbol_id_mapping is
        provided, already-resolved target_symbol_id values are remapped via
        the mapping instead of being set to NULL.
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
        new_refs: list[ReferenceModel] = []
        for ref in source_refs:
            # Remap target_symbol_id if mapping is available
            old_target = ref.target_symbol_id
            if symbol_id_mapping and old_target and old_target in symbol_id_mapping:
                new_target_symbol_id = symbol_id_mapping[old_target]
            else:
                new_target_symbol_id = None

            new_refs.append(
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
                    target_symbol_id=new_target_symbol_id,
                    target_repository_id=None,
                    # Explicitly set indexed_at to current time
                    indexed_at=now,
                )
            )

        self.session.add_all(new_refs)
        await self.session.flush()
        return len(new_refs)

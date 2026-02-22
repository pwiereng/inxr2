"""PostgreSQL reference repository adapter."""

from sqlalchemy import Subquery, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import ReferenceRepositoryPort
from ....domain.entities import Reference
from ..mappers import ReferenceMapper
from ..models.branch_commit import BranchCommitModel
from ..models.commit import CommitModel
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel
from ..models.reference import ReferenceModel
from ..models.repository import RepositoryModel
from .regex_utils import translate_word_boundaries, validate_regex_pattern


class PostgresReferenceRepository(ReferenceRepositoryPort):
    """PostgreSQL implementation of ReferenceRepositoryPort."""

    def __init__(self, session: AsyncSession):
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

        With content-addressable file versions, references belong to file
        versions. When commit_id is provided, we filter via commit_files
        to show only references from files at that commit.

        Note: ``branch`` scopes the latest-file dedup to that branch's
        commits. It requires a repository context (inferred from the
        symbol's references).
        """
        if commit_id is not None:
            # Time travel mode: filter via commit_files junction
            query = (
                select(ReferenceModel)
                .join(
                    CommitFileModel,
                    CommitFileModel.file_id == ReferenceModel.source_file_id,
                )
                .where(
                    ReferenceModel.target_symbol_id == symbol_id,
                    CommitFileModel.commit_id == commit_id,
                )
            )

            result = await self.session.execute(
                query.order_by(ReferenceModel.source_line).limit(limit)
            )
            models = result.scalars().all()
            return [self.mapper.to_domain(model) for model in models]

        # Default: get from latest version of each file.
        # Deduplicate by filtering to only the latest file version per path.
        # When branch is set, dedup is scoped to that branch.
        latest_sq = self._latest_file_ids_subquery(branch=branch)
        result = await self.session.execute(
            select(ReferenceModel)
            .where(
                ReferenceModel.target_symbol_id == symbol_id,
                ReferenceModel.source_file_id.in_(select(latest_sq.c.max_id)),
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

        With content-addressable file versions, each file version has unique
        references. When commit_id is provided, filters via commit_files.

        Note: ``branch`` scopes the latest-file dedup to that branch's
        commits. It requires ``repository_id`` to take effect.
        """
        if commit_id is not None:
            # Time travel mode: filter via commit_files junction
            query = (
                select(ReferenceModel)
                .join(
                    CommitFileModel,
                    CommitFileModel.file_id == ReferenceModel.source_file_id,
                )
                .where(
                    ReferenceModel.reference_text == text,
                    ReferenceModel.repository_id == repository_id,
                    CommitFileModel.commit_id == commit_id,
                )
            )

            result = await self.session.execute(
                query.order_by(
                    ReferenceModel.source_file_id, ReferenceModel.source_line
                ).limit(limit)
            )
            models = result.scalars().all()
            return [self.mapper.to_domain(model) for model in models]

        # Default: deduplicate by filtering to latest file version per path.
        # When branch is set, dedup is scoped to that branch.
        latest_sq = self._latest_file_ids_subquery(repository_id, branch=branch)
        result = await self.session.execute(
            select(ReferenceModel)
            .where(
                ReferenceModel.reference_text == text,
                ReferenceModel.repository_id == repository_id,
                ReferenceModel.source_file_id.in_(select(latest_sq.c.max_id)),
            )
            .order_by(ReferenceModel.source_file_id, ReferenceModel.source_line)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    def _latest_file_ids_subquery(
        self,
        repository_id: int | None = None,
        branch: str | None = None,
    ) -> Subquery:
        """Subquery returning the latest file ID per (repository_id, path).

        Uses commit dates via commit_files junction to determine "latest",
        which is correct even for HEAD-first indexing where newer commits
        may have lower file IDs.

        When branch is provided, only considers files from commits on that
        branch, so "latest" is scoped to the branch rather than global.
        """
        inner_query = (
            select(
                FileModel.id.label("file_id"),
                func.row_number()
                .over(
                    partition_by=[FileModel.repository_id, FileModel.path],
                    order_by=[
                        CommitModel.commit_date.desc(),
                        CommitModel.id.desc(),
                    ],
                )
                .label("rn"),
            )
            .join(CommitFileModel, CommitFileModel.file_id == FileModel.id)
            .join(CommitModel, CommitModel.id == CommitFileModel.commit_id)
        )
        if repository_id is not None:
            inner_query = inner_query.where(FileModel.repository_id == repository_id)
        if branch is not None:
            join_cond = BranchCommitModel.commit_id == CommitFileModel.commit_id
            if repository_id is not None:
                join_cond = join_cond & (
                    BranchCommitModel.repository_id == repository_id
                )
            inner_query = inner_query.join(
                BranchCommitModel,
                join_cond & (BranchCommitModel.branch == branch),
            )
        inner = inner_query.subquery()
        return select(inner.c.file_id.label("max_id")).where(inner.c.rn == 1).subquery()

    async def search_by_text(
        self,
        query: str,
        repository_id: int | None = None,
        branch: str | None = None,
        scope: str | None = None,
        extensions: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        mode: str | None = None,
        case_sensitive: bool = True,
    ) -> tuple[list[Reference], int]:
        """Search references by text match on reference_text."""
        if mode == "regex":
            validate_regex_pattern(query)
            pg_pattern = translate_word_boundaries(query)
            op = "~" if case_sensitive else "~*"
            base_query = select(ReferenceModel).where(
                ReferenceModel.reference_text.op(op)(pg_pattern)
            )
        else:
            escaped = (
                query.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
            )
            if case_sensitive:
                base_query = select(ReferenceModel).where(
                    ReferenceModel.reference_text.like(f"%{escaped}%", escape="\\")
                )
            else:
                base_query = select(ReferenceModel).where(
                    ReferenceModel.reference_text.ilike(f"%{escaped}%", escape="\\")
                )

        if repository_id is not None:
            base_query = base_query.where(ReferenceModel.repository_id == repository_id)
            # Scope to latest files for this repo/branch
            latest_sq = self._latest_file_ids_subquery(repository_id, branch=branch)
            base_query = base_query.where(
                ReferenceModel.source_file_id.in_(select(latest_sq.c.max_id))
            )
        elif scope == "latest":
            # Global scope: filter to HEAD files across all repos
            head_fids = self._head_file_ids_subquery()
            base_query = base_query.where(
                ReferenceModel.source_file_id.in_(select(head_fids.c.file_id))
            )

        # Apply extension filter via files table
        if extensions is not None and len(extensions) > 0:
            base_query = base_query.where(
                ReferenceModel.source_file_id.in_(
                    select(FileModel.id).where(FileModel.extension.in_(extensions))
                )
            )

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Fetch paginated results
        results_query = (
            base_query.order_by(
                ReferenceModel.repository_id,
                ReferenceModel.source_file_id,
                ReferenceModel.source_line,
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(results_query)
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models], total

    def _head_file_ids_subquery(self) -> Subquery:
        """File IDs at HEAD of each repo's default branch.

        Replicates the pattern from PostgresTextSearch for global scope filtering.
        """
        # Step 1: HEAD commit per repo (latest commit on default branch)
        inner = (
            select(
                RepositoryModel.id.label("repo_id"),
                BranchCommitModel.commit_id.label("commit_id"),
                func.row_number()
                .over(
                    partition_by=RepositoryModel.id,
                    order_by=[
                        CommitModel.commit_date.desc(),
                        CommitModel.id.desc(),
                    ],
                )
                .label("rn"),
            )
            .join(
                BranchCommitModel,
                (BranchCommitModel.repository_id == RepositoryModel.id)
                & (BranchCommitModel.branch == RepositoryModel.default_branch),
            )
            .join(CommitModel, CommitModel.id == BranchCommitModel.commit_id)
            .subquery()
        )
        head_commits = select(inner.c.commit_id).where(inner.c.rn == 1).subquery()

        # Step 2: File IDs at those HEAD commits
        return (
            select(CommitFileModel.file_id.label("file_id"))
            .where(CommitFileModel.commit_id.in_(select(head_commits.c.commit_id)))
            .subquery()
        )

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
    ) -> int:
        """Resolve a batch of unlinked references.

        With content-addressable file versions, symbols are unique per file
        version (no commit_id ambiguity), so we always match cross-file.

        Resolution priority (deterministic):
        1. Same file - most likely the correct local symbol
        2. Same language - cross-file but same language preferred
        3. Lowest symbol ID - deterministic tiebreaker for consistency
        """
        total_resolved = 0

        # Pass 1: Same-file resolution (preferred)
        result = await self.session.execute(
            text("""
                UPDATE "references"
                SET target_symbol_id = sub.target_id
                FROM (
                    SELECT r.id AS ref_id, best.min_id AS target_id
                    FROM "references" r
                    JOIN (
                        SELECT s.name, s.file_id, MIN(s.id) AS min_id
                        FROM symbols s
                        WHERE s.repository_id = :repo_id
                        GROUP BY s.name, s.file_id
                    ) best ON r.reference_text = best.name
                        AND r.source_file_id = best.file_id
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
        remaining = batch_size - total_resolved
        if remaining > 0:
            result = await self.session.execute(
                text("""
                    UPDATE "references"
                    SET target_symbol_id = sub.target_id
                    FROM (
                        SELECT r.id AS ref_id, best.min_id AS target_id
                        FROM "references" r
                        JOIN files rf ON r.source_file_id = rf.id
                        JOIN (
                            SELECT s.name, f.language, MIN(s.id) AS min_id
                            FROM symbols s
                            JOIN files f ON s.file_id = f.id
                            WHERE s.repository_id = :repo_id
                            GROUP BY s.name, f.language
                        ) best ON r.reference_text = best.name
                            AND rf.language = best.language
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
        remaining = batch_size - total_resolved
        if remaining > 0:
            result = await self.session.execute(
                text("""
                    UPDATE "references"
                    SET target_symbol_id = sub.target_id
                    FROM (
                        SELECT r.id AS ref_id, best.min_id AS target_id
                        FROM "references" r
                        JOIN (
                            SELECT s.name, MIN(s.id) AS min_id
                            FROM symbols s
                            WHERE s.repository_id = :repo_id
                            GROUP BY s.name
                        ) best ON r.reference_text = best.name
                        WHERE r.repository_id = :repo_id
                          AND r.target_symbol_id IS NULL
                        LIMIT :batch_size
                    ) sub
                    WHERE "references".id = sub.ref_id
                """),
                {"repo_id": repository_id, "batch_size": remaining},
            )
            total_resolved += result.rowcount or 0  # type: ignore[attr-defined]

        return total_resolved

    async def resolve_unlinked_references(self, repository_id: int) -> int:
        """Resolve references to their target symbols.

        With content-addressable file versions, symbols are unique per file
        version, so no commit-aware mode is needed. Simply match reference_text
        to symbol names across the repository.
        """
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

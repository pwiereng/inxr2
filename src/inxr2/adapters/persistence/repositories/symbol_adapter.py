"""PostgreSQL symbol repository adapter."""

from sqlalchemy import Subquery, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import SymbolRepositoryPort
from ....domain.entities import Symbol
from ..mappers import SymbolMapper
from ..models.branch_commit import BranchCommitModel
from ..models.commit import CommitModel
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel
from ..models.repository import RepositoryModel
from ..models.symbol import SymbolModel
from .regex_utils import translate_word_boundaries, validate_regex_pattern


class PostgresSymbolRepository(SymbolRepositoryPort):
    """PostgreSQL implementation of SymbolRepositoryPort."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.mapper = SymbolMapper()

    async def save(self, symbol: Symbol) -> Symbol:
        """Save or update a symbol."""
        model = self.mapper.to_model(symbol)

        if symbol.id is None:
            self.session.add(model)
        else:
            model = await self.session.merge(model)

        await self.session.flush()
        await self.session.refresh(model)

        return self.mapper.to_domain(model)

    async def save_many(self, symbols: list[Symbol]) -> list[Symbol]:
        """Bulk save symbols for performance."""
        if not symbols:
            return []

        models = [self.mapper.to_model(symbol) for symbol in symbols]
        self.session.add_all(models)
        await self.session.flush()

        for model in models:
            await self.session.refresh(model)

        return [self.mapper.to_domain(model) for model in models]

    async def find_by_id(self, symbol_id: int) -> Symbol | None:
        """Find symbol by ID."""
        result = await self.session.execute(
            select(SymbolModel).where(SymbolModel.id == symbol_id)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    def _latest_file_ids_subquery(
        self, repository_id: int, branch: str | None = None
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
                    partition_by=FileModel.path,
                    order_by=[
                        CommitModel.commit_date.desc(),
                        CommitModel.id.desc(),
                    ],
                )
                .label("rn"),
            )
            .join(CommitFileModel, CommitFileModel.file_id == FileModel.id)
            .join(CommitModel, CommitModel.id == CommitFileModel.commit_id)
            .where(FileModel.repository_id == repository_id)
        )
        if branch is not None:
            inner_query = inner_query.join(
                BranchCommitModel,
                (BranchCommitModel.commit_id == CommitFileModel.commit_id)
                & (BranchCommitModel.repository_id == repository_id)
                & (BranchCommitModel.branch == branch),
            )
        inner = inner_query.subquery()
        return select(inner.c.file_id.label("max_id")).where(inner.c.rn == 1).subquery()

    def _head_file_ids_subquery(self) -> Subquery:
        """File IDs at HEAD of each repo's default branch (for global search)."""
        inner = (
            select(
                RepositoryModel.id.label("repo_id"),
                BranchCommitModel.commit_id.label("commit_id"),
                func.row_number()
                .over(
                    partition_by=RepositoryModel.id,
                    order_by=[CommitModel.commit_date.desc(), CommitModel.id.desc()],
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

        return (
            select(CommitFileModel.file_id.label("file_id"))
            .where(CommitFileModel.commit_id.in_(select(head_commits.c.commit_id)))
            .subquery()
        )

    async def search_by_name(
        self,
        name: str,
        repository_id: int | None = None,
        kind: str | None = None,
        limit: int = 50,
        branch: str | None = None,
        language: str | None = None,
        extensions: list[str] | None = None,
        scope: str | None = None,
        mode: str | None = None,
        case_sensitive: bool = True,
    ) -> list[Symbol]:
        """Search symbols by name (supports autocomplete).

        When repository_id is provided, deduplicates by filtering to
        only the latest file version per (repository_id, path).
        When scope is "latest" and repository_id is None, filters to
        symbols from files at HEAD of each repo's default branch.

        Note: ``branch`` only takes effect when ``repository_id`` is
        provided, since branch-scoped dedup requires a repository context.
        """
        if mode == "regex":
            validate_regex_pattern(name)
            pg_pattern = translate_word_boundaries(name)
            op = "~" if case_sensitive else "~*"
            query = select(SymbolModel).where(SymbolModel.name.op(op)(pg_pattern))
        else:
            escaped = name.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
            if case_sensitive:
                query = select(SymbolModel).where(
                    SymbolModel.name.like(f"%{escaped}%", escape="\\")
                )
            else:
                query = select(SymbolModel).where(
                    SymbolModel.name.ilike(f"%{escaped}%", escape="\\")
                )

        if repository_id is None and scope == "latest":
            # Global search: only symbols from HEAD of each repo's default branch
            head_fids = self._head_file_ids_subquery()
            query = query.where(SymbolModel.file_id.in_(select(head_fids.c.file_id)))
        elif repository_id is not None:
            query = query.where(SymbolModel.repository_id == repository_id)
            # Deduplicate: only symbols from latest file version per path.
            # When branch is set, dedup is scoped to that branch.
            latest_sq = self._latest_file_ids_subquery(repository_id, branch=branch)
            query = query.where(SymbolModel.file_id.in_(select(latest_sq.c.max_id)))

        if kind is not None:
            query = query.where(SymbolModel.kind == kind)

        if language is not None:
            query = query.where(
                SymbolModel.file_id.in_(
                    select(FileModel.id).where(FileModel.language == language)
                )
            )

        if extensions is not None and len(extensions) > 0:
            query = query.where(
                SymbolModel.file_id.in_(
                    select(FileModel.id).where(FileModel.extension.in_(extensions))
                )
            )

        query = query.order_by(SymbolModel.name).limit(limit)

        result = await self.session.execute(query)
        models = result.scalars().all()

        return [self.mapper.to_domain(model) for model in models]

    async def find_by_exact_name(
        self,
        name: str,
        repository_id: int | None = None,
        commit_id: int | None = None,
    ) -> list[Symbol]:
        """Find all symbols with the exact given name.

        Args:
            name: The exact symbol name to match
            repository_id: Filter by repository (optional)
            commit_id: Filter by specific commit via commit_files (optional).
        """
        query = select(SymbolModel).where(SymbolModel.name == name)

        if repository_id is not None:
            query = query.where(SymbolModel.repository_id == repository_id)

        if commit_id is not None:
            # Filter via commit_files junction
            query = query.where(
                SymbolModel.file_id.in_(
                    select(CommitFileModel.file_id).where(
                        CommitFileModel.commit_id == commit_id
                    )
                )
            )
        elif repository_id is not None:
            # Default mode: only latest file version per path
            latest_sq = self._latest_file_ids_subquery(repository_id)
            query = query.where(SymbolModel.file_id.in_(select(latest_sq.c.max_id)))

        query = query.order_by(SymbolModel.qualified_name, SymbolModel.id)

        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def find_by_qualified_name(
        self, repository_id: int, qualified_name: str
    ) -> list[Symbol]:
        """Find symbols by fully qualified name.

        Deduplicates by filtering to only latest file version per path.
        """
        latest_sq = self._latest_file_ids_subquery(repository_id)
        result = await self.session.execute(
            select(SymbolModel).where(
                SymbolModel.repository_id == repository_id,
                SymbolModel.qualified_name == qualified_name,
                SymbolModel.file_id.in_(select(latest_sq.c.max_id)),
            )
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def list_by_file(self, file_id: int) -> list[Symbol]:
        """List all symbols in a file."""
        result = await self.session.execute(
            select(SymbolModel)
            .where(SymbolModel.file_id == file_id)
            .order_by(SymbolModel.start_line, SymbolModel.start_column)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def delete_by_file(self, file_id: int) -> int:
        """Delete all symbols for a file (for re-indexing). Returns count deleted."""
        result = await self.session.execute(
            delete(SymbolModel).where(SymbolModel.file_id == file_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def count_by_repository(self, repository_id: int) -> int:
        """Count symbols for a repository."""
        result = await self.session.execute(
            select(func.count(SymbolModel.id)).where(
                SymbolModel.repository_id == repository_id
            )
        )
        return result.scalar() or 0

    async def delete_by_repository(self, repository_id: int) -> int:
        """Delete all symbols for a repository. Returns count deleted."""
        result = await self.session.execute(
            delete(SymbolModel).where(SymbolModel.repository_id == repository_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

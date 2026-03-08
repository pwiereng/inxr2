"""Get symbol tree use case for logical view.

Provides a hierarchical view of symbols organised as:
  Tier 1: Files that contain symbols (with counts)
  Tier 2: Top-level symbols in a file (classes, functions, constants)
  Tier 3: Members of a symbol (methods, fields, properties)

Each tier is fetched lazily — the frontend requests one tier at a time.
"""

from dataclasses import dataclass, field

from ....domain.entities import Symbol
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    ReferenceRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
)


@dataclass
class SymbolTreeFile:
    """A file in the symbol tree (tier 1)."""

    file_id: int
    path: str
    language: str | None
    symbol_count: int
    kind_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ResolvedInheritance:
    """Inheritance reference resolved to target symbol location."""

    reference_text: str
    target_symbol_id: int | None = None
    target_file_id: int | None = None
    target_file_path: str | None = None
    target_line: int | None = None


@dataclass
class SymbolTreeNode:
    """A symbol in the tree (tier 2 or 3)."""

    symbol: Symbol
    file_path: str | None
    has_children: bool
    inheritance: list[ResolvedInheritance] = field(default_factory=list)


@dataclass
class GetSymbolTreeRequest:
    """Request for symbol tree data.

    Exactly one of these modes is used per call:
    - Neither file_id nor parent_symbol_id: tier 1 (file list)
    - file_id set, parent_symbol_id not set: tier 2 (top-level symbols)
    - parent_symbol_id set: tier 3 (children of a symbol)

    Args:
        repository_name: Repository name (resolved to ID internally)
        branch: Branch name for temporal scoping (optional)
        commit_hash: Specific commit hash (overrides branch, optional)
        file_id: Expand this file to show its symbols (tier 2)
        parent_symbol_id: Expand this symbol to show its children (tier 3)
        language: Filter files by programming language (tier 1 only)
        kind: Filter symbols by kind (tier 2/3 only)
    """

    repository_name: str
    branch: str | None = None
    commit_hash: str | None = None
    file_id: int | None = None
    parent_symbol_id: int | None = None
    language: str | None = None
    kind: str | None = None
    kinds: list[str] | None = None


@dataclass
class GetSymbolTreeFilesResponse:
    """Response containing tier 1 file list."""

    files: list[SymbolTreeFile]
    repository_id: int
    available_kinds: list[str] = field(default_factory=list)


@dataclass
class GetSymbolTreeSymbolsResponse:
    """Response containing tier 2/3 symbol list."""

    symbols: list[SymbolTreeNode]
    repository_id: int


class GetSymbolTreeUseCase:
    """Use case for fetching symbol tree data.

    Supports lazy loading: each call returns one tier of the hierarchy.
    The frontend expands nodes by making additional requests.
    """

    def __init__(
        self,
        repository_repo: RepositoryPort,
        symbol_repo: SymbolRepositoryPort,
        file_repo: FileRepositoryPort,
        reference_repo: ReferenceRepositoryPort,
        commit_repo: CommitRepositoryPort,
    ) -> None:
        self._repository_repo = repository_repo
        self._symbol_repo = symbol_repo
        self._file_repo = file_repo
        self._reference_repo = reference_repo
        self._commit_repo = commit_repo

    async def execute(
        self, request: GetSymbolTreeRequest
    ) -> GetSymbolTreeFilesResponse | GetSymbolTreeSymbolsResponse:
        """Execute the symbol tree request.

        Returns either a file list (tier 1) or a symbol list (tier 2/3)
        depending on which parameters are provided.

        Raises:
            ValueError: If repository or commit cannot be found
        """
        # Resolve repository
        repo = await self._repository_repo.find_by_name(request.repository_name)
        if not repo or repo.id is None:
            raise ValueError(f"Repository '{request.repository_name}' not found")
        repository_id = repo.id

        # Resolve commit_id if commit_hash provided
        commit_id = await self._resolve_commit_id(repository_id, request.commit_hash)

        if request.parent_symbol_id is not None:
            # Tier 3: children of a symbol
            return await self._get_symbol_children(
                repository_id, request.parent_symbol_id, request.kind, commit_id
            )
        elif request.file_id is not None:
            # Tier 2: top-level symbols in a file
            return await self._get_file_symbols(
                repository_id, request.file_id, request.kind, commit_id
            )
        else:
            # Tier 1: files with symbols
            return await self._get_files(
                repository_id,
                request.branch,
                commit_id,
                request.language,
                request.kinds,
            )

    async def _resolve_commit_id(
        self, repository_id: int, commit_hash: str | None
    ) -> int | None:
        """Resolve commit hash to commit ID."""
        if commit_hash is None:
            return None
        commit = await self._commit_repo.find_by_hash(repository_id, commit_hash)
        if not commit:
            raise ValueError(
                f"Commit '{commit_hash}' not found for repository {repository_id}"
            )
        return commit.id

    async def _get_files(
        self,
        repository_id: int,
        branch: str | None,
        commit_id: int | None,
        language: str | None,
        kinds: list[str] | None = None,
    ) -> GetSymbolTreeFilesResponse:
        """Tier 1: list files that contain symbols."""
        rows = await self._symbol_repo.list_files_with_symbols(
            repository_id=repository_id,
            branch=branch,
            commit_id=commit_id,
            language=language,
            kinds=kinds,
        )
        file_ids = [file_id for file_id, _, _, _ in rows]

        # Batch-fetch kind counts for all files
        kind_counts_by_file = await self._symbol_repo.count_top_level_kinds_by_file(
            file_ids
        )

        files = [
            SymbolTreeFile(
                file_id=file_id,
                path=path,
                language=lang,
                symbol_count=count,
                kind_counts=kind_counts_by_file.get(file_id, {}),
            )
            for file_id, path, lang, count in rows
        ]
        # Fetch available kinds (unfiltered by kinds param)
        available_kinds = await self._symbol_repo.list_distinct_top_level_kinds(
            repository_id=repository_id,
            branch=branch,
            commit_id=commit_id,
            language=language,
        )
        return GetSymbolTreeFilesResponse(
            files=files,
            repository_id=repository_id,
            available_kinds=available_kinds,
        )

    async def _get_file_symbols(
        self,
        repository_id: int,
        file_id: int,
        kind: str | None,
        commit_id: int | None = None,
    ) -> GetSymbolTreeSymbolsResponse:
        """Tier 2: top-level symbols in a file."""
        symbols = await self._symbol_repo.list_by_file_and_parent(
            file_id=file_id, parent_symbol_id=None
        )
        return await self._build_symbol_response(
            repository_id, symbols, file_id, kind, commit_id
        )

    async def _get_symbol_children(
        self,
        repository_id: int,
        parent_symbol_id: int,
        kind: str | None,
        commit_id: int | None = None,
    ) -> GetSymbolTreeSymbolsResponse:
        """Tier 3: children of a symbol."""
        # Look up parent to get its file_id
        parent = await self._symbol_repo.find_by_id(parent_symbol_id)
        if not parent:
            raise ValueError(f"Symbol {parent_symbol_id} not found")

        symbols = await self._symbol_repo.list_by_file_and_parent(
            file_id=parent.file_id, parent_symbol_id=parent_symbol_id
        )
        return await self._build_symbol_response(
            repository_id, symbols, parent.file_id, kind, commit_id
        )

    async def _build_symbol_response(
        self,
        repository_id: int,
        symbols: list[Symbol],
        file_id: int,
        kind: str | None,
        commit_id: int | None = None,
    ) -> GetSymbolTreeSymbolsResponse:
        """Build symbol response with has_children and inheritance info."""
        if kind is not None:
            symbols = [s for s in symbols if s.kind.value == kind]

        # Get file path
        file = await self._file_repo.find_by_id(file_id)
        file_path = file.path if file else None

        # Check which symbols have children (batch: all symbols in this file)
        all_file_symbols = await self._symbol_repo.list_by_file(file_id)
        parent_ids_with_children: set[int] = set()
        for s in all_file_symbols:
            if s.parent_symbol_id is not None:
                parent_ids_with_children.add(s.parent_symbol_id)

        # Fetch inheritance references from this file.
        # Inheritance refs are emitted FROM the class definition (source_file_id
        # is the file, reference_text is the superclass name). Match to class
        # symbols by checking if the reference line falls within the symbol's
        # line range.
        inheritance_by_symbol: dict[int, list[ResolvedInheritance]] = {}
        class_like_kinds = {"class", "interface", "struct", "record"}
        class_symbols = [s for s in symbols if s.kind.value in class_like_kinds]
        if class_symbols:
            all_refs = await self._reference_repo.list_by_file(file_id)
            inheritance_refs = [
                r for r in all_refs if r.reference_type.value == "inheritance"
            ]

            # Collect unique base class names to resolve in batch
            base_names: set[str] = set()
            for ref in inheritance_refs:
                base_names.add(ref.reference_text)

            # Resolve each base class name to a target symbol
            resolved_targets: dict[str, Symbol] = {}
            for name in base_names:
                matches = await self._symbol_repo.find_by_exact_name(
                    name, repository_id=repository_id, commit_id=commit_id
                )
                # Prefer class-like symbols
                for m in matches:
                    if m.kind.value in class_like_kinds:
                        resolved_targets[name] = m
                        break
                else:
                    if matches:
                        resolved_targets[name] = matches[0]

            # Look up file paths for resolved targets (batch unique file IDs)
            target_file_paths: dict[int, str] = {}
            target_file_ids = {t.file_id for t in resolved_targets.values()}
            for fid in target_file_ids:
                f = await self._file_repo.find_by_id(fid)
                if f:
                    target_file_paths[fid] = f.path

            # Map refs to class symbols
            for ref in inheritance_refs:
                for cs in class_symbols:
                    if (
                        cs.id is not None
                        and cs.start_line <= ref.source_line <= cs.end_line
                    ):
                        target = resolved_targets.get(ref.reference_text)
                        resolved = ResolvedInheritance(
                            reference_text=ref.reference_text,
                            target_symbol_id=target.id if target else None,
                            target_file_id=target.file_id if target else None,
                            target_file_path=(
                                target_file_paths.get(target.file_id)
                                if target
                                else None
                            ),
                            target_line=(target.start_line if target else None),
                        )
                        inheritance_by_symbol.setdefault(cs.id, []).append(resolved)
                        break

        nodes = [
            SymbolTreeNode(
                symbol=s,
                file_path=file_path,
                has_children=s.id in parent_ids_with_children,
                inheritance=inheritance_by_symbol.get(s.id or 0, []),
            )
            for s in symbols
        ]

        return GetSymbolTreeSymbolsResponse(symbols=nodes, repository_id=repository_id)

"""Resolve references use case.

This use case handles the post-indexing step of matching references
to their target symbols in the codebase.
"""

from collections.abc import Callable
from dataclasses import dataclass

from ...ports.repositories import ReferenceRepositoryPort


@dataclass
class ResolutionProgress:
    """Progress information during reference resolution."""

    resolved: int
    total: int
    preparing: bool = False
    prepare_stage: str = ""

    @property
    def percent(self) -> int:
        """Calculate percentage complete."""
        if self.total == 0:
            return 100
        return int((self.resolved / self.total) * 100)


# Type alias for progress callback
ResolutionProgressCallback = Callable[[ResolutionProgress], None]


@dataclass
class ResolveReferencesRequest:
    """Request to resolve unlinked references in a repository.

    Args:
        repository_id: The repository ID to resolve references for
        branch: Optional branch to scope resolution to. When set,
            only references from files on that branch are resolved.
    """

    repository_id: int
    branch: str | None = None


@dataclass
class ResolveReferencesResponse:
    """Response from resolving references.

    Args:
        resolved_count: Number of references that were resolved
    """

    resolved_count: int


class ResolveReferencesUseCase:
    """Use case for resolving references to their target symbols.

    After indexing, this use case matches reference_text to symbol names
    and updates the target_symbol_id for each reference. This enables
    "find usages" and "go to definition" functionality.

    With content-addressable file versions, symbols are unique per file
    version (no commit_id ambiguity), so commit-aware mode is not needed.

    Dependencies are injected via constructor.
    """

    def __init__(self, reference_repository: ReferenceRepositoryPort) -> None:
        self._reference_repository = reference_repository

    async def execute(
        self, request: ResolveReferencesRequest
    ) -> ResolveReferencesResponse:
        """Execute reference resolution."""
        resolved_count = await self._reference_repository.resolve_unlinked_references(
            repository_id=request.repository_id,
            branch=request.branch,
        )

        return ResolveReferencesResponse(resolved_count=resolved_count)

    async def execute_with_progress(
        self,
        request: ResolveReferencesRequest,
        progress_callback: ResolutionProgressCallback | None = None,
        batch_size: int = 5000,
    ) -> ResolveReferencesResponse:
        """Execute reference resolution with progress updates.

        Resolves references in batches, calling the progress callback
        after each batch to report progress. Uses a large default
        batch_size (5000) to balance memory usage against the
        O(N²/batch_size) scanning cost of small batches.

        When request.branch is set, resolution is scoped to that branch:
        prepare_resolution builds branch-scoped temp tables, and
        count_unresolved_references uses them for an accurate count.
        The prepare step runs BEFORE the count so the count can leverage
        the branch-scoped temp table.
        """
        # Pre-compute lookup tables FIRST so the count query can use
        # the branch-scoped temp table (when branch is set).
        total_resolved = 0

        def on_prepare_stage(stage: str) -> None:
            if progress_callback:
                progress_callback(
                    ResolutionProgress(
                        resolved=0,
                        total=0,
                        preparing=True,
                        prepare_stage=stage,
                    )
                )

        on_prepare_stage("Preparing symbol lookup tables...")

        await self._reference_repository.prepare_resolution(
            repository_id=request.repository_id,
            progress_callback=on_prepare_stage,
            branch=request.branch,
        )

        # Count AFTER prepare so the count uses branch-scoped temp tables
        total_unresolved = await self._reference_repository.count_unresolved_references(
            repository_id=request.repository_id
        )

        if total_unresolved == 0:
            if progress_callback:
                progress_callback(ResolutionProgress(resolved=0, total=0))
            return ResolveReferencesResponse(resolved_count=0)

        if progress_callback:
            progress_callback(ResolutionProgress(resolved=0, total=total_unresolved))

        # Resolve in batches
        while True:
            batch_resolved = await self._reference_repository.resolve_references_batch(
                repository_id=request.repository_id,
                batch_size=batch_size,
            )

            if batch_resolved == 0:
                break

            total_resolved += batch_resolved

            if progress_callback:
                progress_callback(
                    ResolutionProgress(resolved=total_resolved, total=total_unresolved)
                )

        return ResolveReferencesResponse(resolved_count=total_resolved)

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
        commit_aware: If True, only match references to symbols from the
                     same commit (for time travel consistency). If False,
                     match across all commits in the repository.
    """

    repository_id: int
    commit_aware: bool = False


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

    Two modes are supported:
    - commit_aware=False: Match references to any symbol in the repository
      (useful for incremental indexing where symbols may exist in other commits)
    - commit_aware=True: Only match references to symbols from the same commit
      (ensures time travel navigation stays within a consistent version)

    Dependencies are injected via constructor.
    """

    def __init__(self, reference_repository: ReferenceRepositoryPort) -> None:
        """Initialize use case.

        Args:
            reference_repository: Repository for accessing references
        """
        self._reference_repository = reference_repository

    async def execute(
        self, request: ResolveReferencesRequest
    ) -> ResolveReferencesResponse:
        """Execute reference resolution.

        Args:
            request: Resolution request parameters

        Returns:
            Resolution results with count of resolved references
        """
        resolved_count = await self._reference_repository.resolve_unlinked_references(
            repository_id=request.repository_id,
            commit_aware=request.commit_aware,
        )

        return ResolveReferencesResponse(resolved_count=resolved_count)

    async def execute_with_progress(
        self,
        request: ResolveReferencesRequest,
        progress_callback: ResolutionProgressCallback | None = None,
        batch_size: int = 1000,
    ) -> ResolveReferencesResponse:
        """Execute reference resolution with progress updates.

        Resolves references in batches, calling the progress callback
        after each batch to report progress.

        Args:
            request: Resolution request parameters
            progress_callback: Optional callback for progress updates
            batch_size: Number of references to process per batch

        Returns:
            Resolution results with count of resolved references
        """
        # Get total count of unresolved references
        total_unresolved = await self._reference_repository.count_unresolved_references(
            repository_id=request.repository_id
        )

        if total_unresolved == 0:
            if progress_callback:
                progress_callback(ResolutionProgress(resolved=0, total=0))
            return ResolveReferencesResponse(resolved_count=0)

        # Report initial progress
        total_resolved = 0
        if progress_callback:
            progress_callback(ResolutionProgress(resolved=0, total=total_unresolved))

        # Resolve in batches
        while True:
            batch_resolved = await self._reference_repository.resolve_references_batch(
                repository_id=request.repository_id,
                batch_size=batch_size,
                commit_aware=request.commit_aware,
            )

            if batch_resolved == 0:
                break

            total_resolved += batch_resolved

            if progress_callback:
                progress_callback(
                    ResolutionProgress(resolved=total_resolved, total=total_unresolved)
                )

        return ResolveReferencesResponse(resolved_count=total_resolved)

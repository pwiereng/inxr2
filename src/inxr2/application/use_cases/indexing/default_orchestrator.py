"""
Default implementation of IndexingOrchestratorPort.

This orchestrator coordinates the indexing workflow, delegating per-file
and per-commit processing to focused use cases (ProcessFileUseCase,
ProcessCommitUseCase) while keeping the orchestration logic here.
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from inxr2.domain.entities import IndexStatus

from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    IndexStatusRepositoryPort,
    ReferenceRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
    TextContentRepositoryPort,
)
from ...ports.services import (
    CommitInfo,
    GitServicePort,
    IndexingOrchestratorPort,
    ParserServicePort,
    PlaintextParserPort,
)
from .orchestrator import (
    DBQueryStats,
    IndexRepositoryRequest,
    IndexRepositoryResponse,
)
from .process_commit import (
    ProcessCommitRequest,
    ProcessCommitResult,
    ProcessCommitUseCase,
)
from .process_file import ProcessFileUseCase
from .resolve_references import (
    ResolutionProgress,
    ResolveReferencesRequest,
    ResolveReferencesUseCase,
)


@dataclass
class IndexingProgress:
    """Progress information during indexing."""

    phase: str  # "files", "resolving"
    files_processed: int
    files_total: int
    symbols_found: int = 0
    references_found: int = 0
    # Resolution progress (only set during "resolving" phase)
    refs_resolved: int = 0
    refs_total: int = 0
    refs_preparing: bool = False
    refs_prepare_stage: str = ""


# Type alias for progress callback
ProgressCallback = Callable[[IndexingProgress], None]


class DefaultIndexingOrchestrator(IndexingOrchestratorPort):
    """
    Coordinates the indexing workflow by delegating to focused use cases.

    Workflow:
    1. Prepare repository (get or create in DB)
    2. Incremental detection (check last indexed commit)
    3. Commit selection (incremental/branch/full)
    4. File counting for progress
    5. Delegate each commit to ProcessCommitUseCase, aggregate results
    6. Resolve references via ResolveReferencesUseCase
    7. Update index status
    8. Return IndexRepositoryResponse
    """

    def __init__(
        self,
        repository_repo: RepositoryPort,
        commit_repo: CommitRepositoryPort,
        file_repo: FileRepositoryPort,
        symbol_repo: SymbolRepositoryPort,
        reference_repo: ReferenceRepositoryPort,
        index_status_repo: IndexStatusRepositoryPort,
        text_content_repo: TextContentRepositoryPort,
        git_service: GitServicePort,
        parser_service: ParserServicePort,
        plaintext_parser: PlaintextParserPort,
        pre_resolve_callback: Callable[[], Awaitable[None]] | None = None,
        post_commit_callback: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._repository_repo = repository_repo
        self._index_status_repo = index_status_repo
        self._git_service = git_service
        self._file_repo = file_repo
        self._pre_resolve_callback = pre_resolve_callback
        self._post_commit_callback = post_commit_callback

        # Build internal use cases
        self._process_file_use_case = ProcessFileUseCase(
            git_service=git_service,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=parser_service,
            plaintext_parser=plaintext_parser,
        )
        self._process_commit_use_case = ProcessCommitUseCase(
            commit_repo=commit_repo,
            file_repo=file_repo,
            git_service=git_service,
            text_content_repo=text_content_repo,
            process_file_use_case=self._process_file_use_case,
        )
        self._resolve_refs_use_case = ResolveReferencesUseCase(
            reference_repository=reference_repo,
        )

    async def index_repository(
        self,
        request: IndexRepositoryRequest,
        progress_callback: ProgressCallback | None = None,
    ) -> IndexRepositoryResponse:
        """Index a repository with specified strategy."""
        start_time = time.monotonic()
        db_stats = DBQueryStats()

        # Step 1: Prepare repository
        repo_name = request.repository_path.name
        repository, created = await self._repository_repo.get_or_create(
            name=repo_name,
            url=str(request.repository_path),
            default_branch=request.branch or "main",
        )
        db_stats.selects += 1
        if created:
            db_stats.inserts += 1
        repo_id = repository.id
        assert repo_id is not None, "Repository must have an ID after save"
        branch = request.branch or "main"

        # Step 2: Incremental detection
        all_statuses = await self._index_status_repo.list_by_repository(
            repository_id=repo_id
        )
        db_stats.selects += 1
        filtered_statuses = [s for s in all_statuses if s.branch == branch]
        index_status = filtered_statuses[0] if filtered_statuses else None
        last_indexed_hash = index_status.last_indexed_commit if index_status else None

        current_head = self._git_service.get_current_commit(
            repo_path=request.repository_path,
            branch=branch,
        )

        # Step 3: Commit selection
        commits_data = self._select_commits(
            request, branch, last_indexed_hash, current_head
        )
        newest_commit = commits_data[0] if commits_data else None
        oldest_commit = commits_data[-1] if commits_data else None

        # Step 4: Count files at HEAD for progress estimation.
        # Only query HEAD commit instead of all commits (saves 133 git ls-tree calls).
        # Total files is an estimate; corrected from actual counts after processing.
        files_at_head = 0
        if commits_data:
            head_files = self._git_service.list_files(
                repo_path=request.repository_path,
                commit_hash=commits_data[0].hash,
            )
            files_at_head = len(head_files)
        total_files = files_at_head * len(commits_data)

        if progress_callback:
            progress_callback(
                IndexingProgress(
                    phase="files",
                    files_processed=0,
                    files_total=total_files,
                )
            )

        # Step 5: Process commits — aggregate typed results
        commits_indexed = 0
        agg = ProcessCommitResult()  # running aggregate
        all_errors: list[str] = []
        # Shared blob→content_hash mapping across all commits
        blob_to_content_hash: dict[str, str] = {}
        # Pre-load all existing file versions ONCE (1 query replaces 47K per-file queries).
        # The dict is mutable — new versions are added during processing.
        file_version_index = await self._file_repo.load_file_version_index(repo_id)

        for _i, commit_data in enumerate(commits_data):
            commit_request = ProcessCommitRequest(
                repository_id=repo_id,
                commit_data=commit_data,
                repo_path=request.repository_path,
                branch=branch,
                blob_to_content_hash=blob_to_content_hash,
                file_version_index=file_version_index,
            )

            def on_file_progress(cr: ProcessCommitResult) -> None:
                if progress_callback:
                    progress_callback(
                        IndexingProgress(
                            phase="files",
                            files_processed=agg.files_processed + cr.files_processed,
                            files_total=total_files,
                            symbols_found=agg.symbols_found + cr.symbols_found,
                            references_found=agg.references_found + cr.references_found,
                        )
                    )

            cr = await self._process_commit_use_case.execute(
                commit_request,
                progress_callback=on_file_progress,
            )
            self._merge_commit_result(agg, cr)
            all_errors.extend(cr.errors)
            if not cr.commit_skipped:
                commits_indexed += 1

            # Flush pending writes and clear the session identity map between
            # commits.  File lookups use the in-memory file_version_index dict,
            # so expunging ORM objects is safe and keeps dirty-checks fast
            # (~1K objects per commit instead of ~139K cumulative).
            if self._post_commit_callback is not None:
                await self._post_commit_callback()

        # Step 6: Resolve references
        # Prepare the session before resolution (e.g. flush pending changes
        # and clear the identity map).  The session accumulates ~25K+ ORM
        # objects during indexing; expunging them avoids per-flush dirty
        # checks that slow down the raw-SQL resolution queries.
        if self._pre_resolve_callback is not None:
            await self._pre_resolve_callback()

        # Correct total_files from actual counts (estimate may differ from reality)
        total_files = agg.files_processed + agg.files_skipped + agg.files_failed

        db_stats.selects += 1  # initial count query
        indexing_seconds = time.monotonic() - start_time

        def on_resolution_progress(p: ResolutionProgress) -> None:
            if progress_callback:
                progress_callback(
                    IndexingProgress(
                        phase="resolving",
                        files_processed=agg.files_processed,
                        files_total=total_files,
                        symbols_found=agg.symbols_found,
                        references_found=agg.references_found,
                        refs_resolved=p.resolved,
                        refs_total=p.total,
                        refs_preparing=p.preparing,
                        refs_prepare_stage=p.prepare_stage,
                    )
                )
            db_stats.updates += 1

        resolve_start = time.monotonic()
        resolve_response = await self._resolve_refs_use_case.execute_with_progress(
            ResolveReferencesRequest(repository_id=repo_id, branch=branch),
            progress_callback=on_resolution_progress,
            batch_size=100,
        )
        resolving_seconds = time.monotonic() - resolve_start

        # Step 7: Update index status
        last_indexed_commit = commits_data[0].hash if commits_data else current_head
        await self._update_index_status(
            repository_id=repo_id,
            branch=branch,
            commits_indexed=commits_indexed,
            files_indexed=agg.files_processed,
            symbols_indexed=agg.symbols_found,
            references_indexed=agg.references_found,
            last_indexed_commit=last_indexed_commit,
        )
        db_stats.inserts += 1

        # Step 8: Build response
        return IndexRepositoryResponse(
            repository_id=repo_id,
            repository_name=repo_name,
            branch=branch,
            commits_indexed=commits_indexed,
            files_total=total_files,
            files_processed=agg.files_processed,
            files_skipped=agg.files_skipped,
            files_failed=agg.files_failed,
            files_at_head=files_at_head,
            lines_indexed=agg.lines_indexed,
            symbols_found=agg.symbols_found,
            references_found=agg.references_found,
            references_resolved=resolve_response.resolved_count,
            file_versions_new=agg.file_versions_new,
            file_versions_cached=agg.file_versions_cached,
            comments_indexed=agg.comments_indexed,
            docstrings_indexed=agg.docstrings_indexed,
            commit_messages_indexed=agg.commit_messages_indexed,
            non_code_files_indexed=agg.non_code_files_indexed,
            errors=all_errors,
            elapsed_seconds=time.monotonic() - start_time,
            indexing_seconds=indexing_seconds,
            resolving_seconds=resolving_seconds,
            db_stats=db_stats,
            oldest_commit_hash=oldest_commit.short_hash if oldest_commit else None,
            oldest_commit_date=(
                oldest_commit.commit_date.strftime("%Y-%m-%d %H:%M")
                if oldest_commit
                else None
            ),
            newest_commit_hash=newest_commit.short_hash if newest_commit else None,
            newest_commit_date=(
                newest_commit.commit_date.strftime("%Y-%m-%d %H:%M")
                if newest_commit
                else None
            ),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _select_commits(
        self,
        request: IndexRepositoryRequest,
        branch: str,
        last_indexed_hash: str | None,
        current_head: str,
    ) -> list[CommitInfo]:
        """Select which commits to process based on request parameters."""
        seen_hashes: set[str] = set()
        result: list[CommitInfo] = []

        def _add_unique(commits: list[CommitInfo]) -> None:
            for c in commits:
                if c.hash not in seen_hashes:
                    seen_hashes.add(c.hash)
                    result.append(c)

        # Part 1: Forward fill from last_indexed_hash to HEAD
        if last_indexed_hash:
            # Short-circuit: if HEAD hasn't moved and no --days backfill,
            # skip the expensive list_commits call entirely
            if last_indexed_hash == current_head and not request.days:
                return []

            all_commits = self._git_service.list_commits(
                repo_path=request.repository_path,
                branch=branch,
                max_count=None,
            )
            # list_commits returns oldest-first; reverse to newest-first
            # so we walk from HEAD back toward last_indexed_hash
            all_commits.reverse()
            forward_fill: list[CommitInfo] = []
            for c in all_commits:
                if c.hash == last_indexed_hash:
                    break
                forward_fill.append(c)
            else:
                forward_fill = all_commits
            _add_unique(forward_fill)
        elif not request.days:
            head_info = self._git_service.get_commit_info(
                repo_path=request.repository_path,
                commit_hash=current_head,
            )
            _add_unique([head_info])

        # Part 2: If --days, also include commits from N days ago
        if request.days:
            if request.base_branch and request.base_branch != branch:
                day_commits = self._git_service.list_branch_commits(
                    repo_path=request.repository_path,
                    branch=branch,
                    base_branch=request.base_branch,
                    max_count=None,
                    since_days=request.days,
                )
            else:
                day_commits = self._git_service.list_commits(
                    repo_path=request.repository_path,
                    branch=branch,
                    max_count=None,
                    since_days=request.days,
                )
            # Reverse to newest-first for consistent ordering
            day_commits.reverse()
            _add_unique(day_commits)

        # Fall back to HEAD if nothing selected
        if not result:
            head_info = self._git_service.get_commit_info(
                repo_path=request.repository_path,
                commit_hash=current_head,
            )
            result = [head_info]

        return result

    @staticmethod
    def _merge_commit_result(agg: ProcessCommitResult, cr: ProcessCommitResult) -> None:
        """Merge a single commit result into the running aggregate."""
        agg.files_processed += cr.files_processed
        agg.files_skipped += cr.files_skipped
        agg.files_failed += cr.files_failed
        agg.symbols_found += cr.symbols_found
        agg.references_found += cr.references_found
        agg.file_versions_new += cr.file_versions_new
        agg.file_versions_cached += cr.file_versions_cached
        agg.lines_indexed += cr.lines_indexed
        agg.comments_indexed += cr.comments_indexed
        agg.docstrings_indexed += cr.docstrings_indexed
        agg.commit_messages_indexed += cr.commit_messages_indexed
        agg.non_code_files_indexed += cr.non_code_files_indexed

    async def _update_index_status(
        self,
        repository_id: int,
        branch: str,
        commits_indexed: int,
        files_indexed: int,
        symbols_indexed: int,
        references_indexed: int,
        last_indexed_commit: str | None = None,
    ) -> None:
        """Update index status after indexing."""
        from datetime import UTC, datetime

        status = IndexStatus(
            id=None,
            repository_id=repository_id,
            branch=branch,
            indexing_status="completed",
            total_commits_indexed=commits_indexed,
            total_files_indexed=files_indexed,
            total_symbols_indexed=symbols_indexed,
            total_references_indexed=references_indexed,
            last_indexed_commit=last_indexed_commit,
            last_indexed_at=datetime.now(UTC).replace(tzinfo=None),
            indexer_version="0.1.0",
        )
        await self._index_status_repo.save(status)

"""
Default implementation of IndexingOrchestratorPort.

This orchestrator coordinates the indexing workflow, delegating per-file
and per-commit processing to focused use cases (ProcessFileUseCase,
ProcessCommitUseCase) while keeping the orchestration logic here.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
    PlaintextParserPort,
)
from .optimize_file_indexing import OptimizeFileIndexingUseCase
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
    cache_size: int = 0
    # Resolution progress (only set during "resolving" phase)
    refs_resolved: int = 0
    refs_total: int = 0


# Type alias for progress callback
ProgressCallback = Callable[[IndexingProgress], None]


class DefaultIndexingOrchestrator(IndexingOrchestratorPort):
    """
    Coordinates the indexing workflow by delegating to focused use cases.

    Workflow:
    1. Prepare repository (get or create in DB)
    2. Incremental detection (check last indexed commit)
    3. Commit selection (incremental/branch/full)
    4. Content hash cache loading
    5. File counting for progress
    6. Delegate each commit to ProcessCommitUseCase, aggregate results
    7. Resolve references via ResolveReferencesUseCase
    8. Update index status
    9. Return IndexRepositoryResponse
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
        parser_service: Any,  # ParserServicePort
        plaintext_parser: PlaintextParserPort,
    ) -> None:
        self._repository_repo = repository_repo
        self._index_status_repo = index_status_repo
        self._git_service = git_service

        # Build internal use cases
        optimize_use_case = OptimizeFileIndexingUseCase(
            file_repository=file_repo,
            symbol_repository=symbol_repo,
            reference_repository=reference_repo,
        )
        self._process_file_use_case = ProcessFileUseCase(
            git_service=git_service,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=parser_service,
            plaintext_parser=plaintext_parser,
            optimize_use_case=optimize_use_case,
        )
        self._process_commit_use_case = ProcessCommitUseCase(
            commit_repo=commit_repo,
            git_service=git_service,
            text_content_repo=text_content_repo,
            process_file_use_case=self._process_file_use_case,
        )
        self._resolve_refs_use_case = ResolveReferencesUseCase(
            reference_repository=reference_repo,
        )
        self._file_repo = file_repo

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

        # Already up to date — return early
        if last_indexed_hash == current_head:
            return IndexRepositoryResponse(
                repository_id=repo_id,
                repository_name=repo_name,
                branch=branch,
                commits_indexed=0,
                files_total=0,
                files_processed=0,
                files_skipped=0,
                files_failed=0,
                elapsed_seconds=time.monotonic() - start_time,
                db_stats=db_stats,
            )

        # Step 3: Commit selection
        commits_data = self._select_commits(request, branch, last_indexed_hash)

        # Reverse for HEAD-first indexing
        commits_data = list(reversed(commits_data))
        newest_commit = commits_data[0] if commits_data else None
        oldest_commit = commits_data[-1] if commits_data else None

        # Step 4: Content hash cache
        content_hash_cache = await self._file_repo.get_content_hash_to_file_id_map(
            repository_id=repo_id
        )
        db_stats.selects += 1

        # Step 5: Count total files for progress
        total_files = 0
        files_at_head = 0
        for i, commit_data in enumerate(commits_data):
            if i == 0:
                file_paths = self._git_service.list_files(
                    repo_path=request.repository_path,
                    commit_hash=commit_data.hash,
                )
                total_files += len(file_paths)
                files_at_head = len(file_paths)
            else:
                changed = self._git_service.get_changed_files_in_commit(
                    repo_path=request.repository_path,
                    commit_hash=commit_data.hash,
                )
                total_files += len(changed.added) + len(changed.modified)

        if progress_callback:
            progress_callback(
                IndexingProgress(
                    phase="files",
                    files_processed=0,
                    files_total=total_files,
                    cache_size=len(content_hash_cache),
                )
            )

        # Step 6: Process commits — aggregate typed results
        commits_indexed = 0
        agg = ProcessCommitResult()  # running aggregate
        all_errors: list[str] = []

        for i, commit_data in enumerate(commits_data):
            is_head = i == 0
            commit_request = ProcessCommitRequest(
                repository_id=repo_id,
                commit_data=commit_data,
                repo_path=request.repository_path,
                branch=branch,
                content_hash_cache=content_hash_cache,
                is_head_commit=is_head,
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
                            cache_size=len(content_hash_cache),
                        )
                    )

            cr = await self._process_commit_use_case.execute(
                commit_request,
                progress_callback=on_file_progress,
            )
            self._merge_commit_result(agg, cr)
            all_errors.extend(cr.errors)
            commits_indexed += 1

        db_stats.inserts += agg.db_inserts
        db_stats.selects += agg.db_selects

        # Step 7: Resolve references
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
                        cache_size=len(content_hash_cache),
                        refs_resolved=p.resolved,
                        refs_total=p.total,
                    )
                )
            db_stats.updates += 1

        resolve_start = time.monotonic()
        resolve_response = await self._resolve_refs_use_case.execute_with_progress(
            ResolveReferencesRequest(repository_id=repo_id, commit_aware=False),
            progress_callback=on_resolution_progress,
            batch_size=1000,
        )
        resolving_seconds = time.monotonic() - resolve_start

        # Step 8: Update index status
        last_indexed_commit = commits_data[0].hash if commits_data else current_head
        await self._update_index_status(
            repository_id=repo_id,
            branch=branch,
            commits_indexed=commits_indexed,
            files_indexed=agg.files_processed,
            last_indexed_commit=last_indexed_commit,
        )
        db_stats.inserts += 1

        # Step 9: Build response
        return IndexRepositoryResponse(
            repository_id=repo_id,
            repository_name=repo_name,
            branch=branch,
            commits_indexed=commits_indexed,
            files_total=total_files,
            files_processed=agg.files_processed,
            files_skipped=agg.files_skipped,
            files_failed=agg.files_failed,
            files_unchanged=agg.files_unchanged,
            files_at_head=files_at_head,
            lines_indexed=agg.lines_indexed,
            symbols_found=agg.symbols_found,
            references_found=agg.references_found,
            references_resolved=resolve_response.resolved_count,
            files_reused=agg.files_reused,
            symbols_reused=agg.symbols_reused,
            references_reused=agg.references_reused,
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
    ) -> list[CommitInfo]:
        """Select which commits to process based on request parameters."""
        if last_indexed_hash and not request.force:
            # Incremental mode
            commits_data = self._git_service.list_commits(
                repo_path=request.repository_path,
                branch=branch,
                max_count=None,
            )
            found = False
            result: list[CommitInfo] = []
            for c in commits_data:
                if c.hash == last_indexed_hash:
                    found = True
                    continue
                if not found:
                    continue
                result.append(c)
            if not found and commits_data:
                result = list(commits_data)
            commits_data = result
        elif request.base_branch and request.base_branch != branch:
            commits_data = self._git_service.list_branch_commits(
                repo_path=request.repository_path,
                branch=branch,
                base_branch=request.base_branch,
                max_count=request.max_history,
                since_days=request.since_days,
            )
        else:
            commits_data = self._git_service.list_commits(
                repo_path=request.repository_path,
                branch=branch,
                max_count=request.max_history,
                since_days=request.since_days,
            )

        # Fall back to HEAD if no commits matched
        if not commits_data:
            head_hash = self._git_service.get_current_commit(
                repo_path=request.repository_path,
                branch=request.branch or "main",
            )
            commits_data = [
                self._git_service.get_commit_info(
                    repo_path=request.repository_path,
                    commit_hash=head_hash,
                )
            ]
        return commits_data

    @staticmethod
    def _merge_commit_result(agg: ProcessCommitResult, cr: ProcessCommitResult) -> None:
        """Merge a single commit result into the running aggregate."""
        agg.files_processed += cr.files_processed
        agg.files_skipped += cr.files_skipped
        agg.files_failed += cr.files_failed
        agg.files_unchanged += cr.files_unchanged
        agg.symbols_found += cr.symbols_found
        agg.references_found += cr.references_found
        agg.files_reused += cr.files_reused
        agg.symbols_reused += cr.symbols_reused
        agg.references_reused += cr.references_reused
        agg.lines_indexed += cr.lines_indexed
        agg.comments_indexed += cr.comments_indexed
        agg.docstrings_indexed += cr.docstrings_indexed
        agg.commit_messages_indexed += cr.commit_messages_indexed
        agg.non_code_files_indexed += cr.non_code_files_indexed
        agg.db_inserts += cr.db_inserts
        agg.db_selects += cr.db_selects

    async def _update_index_status(
        self,
        repository_id: int,
        branch: str,
        commits_indexed: int,
        files_indexed: int,
        last_indexed_commit: str | None = None,
    ) -> None:
        """Update index status after indexing."""
        status = IndexStatus(
            id=None,
            repository_id=repository_id,
            branch=branch,
            indexing_status="completed",
            total_commits_indexed=commits_indexed,
            total_files_indexed=files_indexed,
            last_indexed_commit=last_indexed_commit,
            indexer_version="0.1.0",
        )
        await self._index_status_repo.save(status)

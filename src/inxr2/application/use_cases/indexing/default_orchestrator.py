"""
Default implementation of IndexingOrchestratorPort.

This orchestrator coordinates the indexing workflow, delegating to
specialized use cases and services while keeping the orchestration
logic separate from CLI concerns.
"""

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from inxr2.domain.entities import (
    Commit,
    File,
    IndexStatus,
    Reference,
    Symbol,
)
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind

from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    IndexStatusRepositoryPort,
    ReferenceRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
)
from ...ports.services import IndexingOrchestratorPort
from .optimize_file_indexing import (
    OptimizeFileIndexingRequest,
    OptimizeFileIndexingUseCase,
)
from .orchestrator import (
    DBQueryStats,
    IncrementalIndexRequest,
    IndexRepositoryRequest,
    IndexRepositoryResponse,
)
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
    Default implementation of indexing orchestration.

    This orchestrator implements the core indexing workflow:
    1. Prepare repository (get or create in DB)
    2. Get commits to process (full or incremental)
    3. Process each commit:
       - Get files in commit
       - For each file:
         * Check content-hash optimization
         * If no match, parse file and extract symbols/references
         * Save to database
    4. Resolve references (link references to target symbols)
    5. Update index status
    6. Return statistics

    This consolidates logic from the monolithic CLI command while
    staying in the application layer.
    """

    def __init__(
        self,
        repository_repo: RepositoryPort,
        commit_repo: CommitRepositoryPort,
        file_repo: FileRepositoryPort,
        symbol_repo: SymbolRepositoryPort,
        reference_repo: ReferenceRepositoryPort,
        index_status_repo: IndexStatusRepositoryPort,
        git_service: Any,  # GitServicePort - not yet in ports
        parser_service: Any,  # ParserServicePort - exists but simpler interface
    ) -> None:
        """
        Initialize orchestrator with all dependencies.

        Args:
            repository_repo: Repository for repository operations
            commit_repo: Repository for commit operations
            file_repo: Repository for file operations
            symbol_repo: Repository for symbol operations
            reference_repo: Repository for reference operations
            index_status_repo: Repository for index status operations
            git_service: Service for git operations
            parser_service: Service for code parsing
        """
        self._repository_repo = repository_repo
        self._commit_repo = commit_repo
        self._file_repo = file_repo
        self._symbol_repo = symbol_repo
        self._reference_repo = reference_repo
        self._index_status_repo = index_status_repo
        self._git_service = git_service
        self._parser_service = parser_service

        # Initialize use cases that will be reused
        self._optimize_use_case = OptimizeFileIndexingUseCase(
            file_repository=file_repo,
            symbol_repository=symbol_repo,
            reference_repository=reference_repo,
        )
        self._resolve_refs_use_case = ResolveReferencesUseCase(
            reference_repository=reference_repo
        )

    async def index_repository(
        self,
        request: IndexRepositoryRequest,
        progress_callback: ProgressCallback | None = None,
    ) -> IndexRepositoryResponse:
        """
        Index a repository with specified strategy.

        This is the main entry point for repository indexing.

        Args:
            request: The indexing request parameters
            progress_callback: Optional callback for progress updates
        """
        start_time = time.monotonic()

        # Statistics tracking
        stats: dict[str, Any] = {
            "commits_indexed": 0,
            "files_total": 0,
            "files_processed": 0,
            "files_skipped": 0,
            "files_failed": 0,
            "files_at_head": 0,
            "lines_indexed": 0,
            "symbols_found": 0,
            "references_found": 0,
            "references_resolved": 0,
            "files_reused": 0,
            "symbols_reused": 0,
            "references_reused": 0,
            "errors": [],
            "db_stats": DBQueryStats(),
        }

        # Step 1: Prepare repository
        repo_name = request.repository_path.name
        # get_or_create: 1 SELECT + 1 INSERT (if new)
        repository, created = await self._repository_repo.get_or_create(
            name=repo_name,
            url=str(request.repository_path),
            default_branch=request.branch or "main",
        )
        stats["db_stats"].selects += 1
        if created:
            stats["db_stats"].inserts += 1
        repo_id = repository.id
        assert repo_id is not None, "Repository must have an ID after save"

        # Step 2: Get commits to process
        # list_commits returns commits from oldest to newest, we reverse for HEAD-first
        commits_data = self._git_service.list_commits(
            repo_path=request.repository_path,
            branch=request.branch or "main",
            max_count=request.max_history,
            since_days=request.since_days,
        )

        # If no commits match the filter (e.g., no commits in last N days),
        # still index the HEAD commit to capture current state
        if not commits_data:
            head_commit_hash = self._git_service.get_current_commit(
                repo_path=request.repository_path,
                branch=request.branch or "main",
            )
            head_commit_info = self._git_service.get_commit_info(
                repo_path=request.repository_path,
                commit_hash=head_commit_hash,
            )
            # Convert to the format expected by _process_commit
            commits_data = [
                {
                    "hash": head_commit_info["hash"],
                    "short_hash": head_commit_info["short_hash"],
                    "author_name": head_commit_info["author_name"],
                    "author_email": head_commit_info["author_email"],
                    "author_date": head_commit_info["author_date"],
                    "committer_name": head_commit_info["committer_name"],
                    "committer_email": head_commit_info["committer_email"],
                    "commit_date": head_commit_info["commit_date"],
                    "message": head_commit_info["message"],
                    "parent_hashes": head_commit_info["parent_hashes"],
                }
            ]

        # Reverse commits for HEAD-first indexing:
        # - HEAD (newest) is processed first with ALL files
        # - Older commits use delta indexing (only changed files)
        # This ensures all files have records, and time-travel queries work correctly
        commits_data = list(reversed(commits_data))

        # Capture commit range info for summary (after reversing: [0]=newest, [-1]=oldest)
        newest_commit = commits_data[0] if commits_data else None
        oldest_commit = commits_data[-1] if commits_data else None

        # Step 3: Build content-hash cache for optimization
        content_hash_cache = await self._file_repo.get_content_hash_to_file_id_map(
            repository_id=repo_id
        )
        stats["db_stats"].selects += 1

        # Step 4: Count total files to process (for progress)
        # HEAD commit: ALL files; other commits: only changed files
        total_files = 0
        for i, commit_data in enumerate(commits_data):
            if i == 0:
                # HEAD commit: count all files
                file_paths = self._git_service.list_files(
                    repo_path=request.repository_path,
                    commit_hash=commit_data["hash"],
                )
                total_files += len(file_paths)
                stats["files_at_head"] = len(file_paths)  # Track HEAD file count
            else:
                # Older commits: count only changed files
                changed = self._git_service.get_changed_files_in_commit(
                    repo_path=request.repository_path,
                    commit_hash=commit_data["hash"],
                )
                total_files += len(changed["added"]) + len(changed["modified"])
        stats["files_total"] = total_files
        stats["files_unchanged"] = 0  # Will be tracked per-commit

        # Report initial progress
        if progress_callback:
            progress_callback(
                IndexingProgress(
                    phase="files",
                    files_processed=0,
                    files_total=total_files,
                    symbols_found=0,
                    references_found=0,
                    cache_size=len(content_hash_cache),
                )
            )

        # Step 5: Process each commit (HEAD first, then older commits)
        last_commit_hash: str | None = None
        for i, commit_data in enumerate(commits_data):
            # First commit is HEAD - process ALL files
            # Subsequent commits use delta indexing (only changed files)
            is_head_commit = i == 0
            await self._process_commit(
                repository_id=repo_id,
                commit_data=commit_data,
                request=request,
                content_hash_cache=content_hash_cache,
                stats=stats,
                progress_callback=progress_callback,
                is_head_commit=is_head_commit,
            )
            stats["commits_indexed"] += 1
            last_commit_hash = commit_data["hash"]

        # Step 6: Resolve references with progress
        def on_resolution_progress(p: ResolutionProgress) -> None:
            if progress_callback:
                progress_callback(
                    IndexingProgress(
                        phase="resolving",
                        files_processed=stats["files_processed"],
                        files_total=stats["files_total"],
                        symbols_found=stats["symbols_found"],
                        references_found=stats["references_found"],
                        cache_size=len(content_hash_cache),
                        refs_resolved=p.resolved,
                        refs_total=p.total,
                    )
                )
            # Track DB operations: each batch is 1 UPDATE
            stats["db_stats"].updates += 1

        # Initial count query
        stats["db_stats"].selects += 1

        resolve_request = ResolveReferencesRequest(
            repository_id=repo_id,
            commit_aware=True,  # Time-travel consistent: resolve to symbols at same commit
        )
        resolve_response = await self._resolve_refs_use_case.execute_with_progress(
            resolve_request,
            progress_callback=on_resolution_progress,
            batch_size=1000,
        )
        stats["references_resolved"] = resolve_response.resolved_count

        # Step 6: Update index status
        await self._update_index_status(
            repository_id=repo_id,
            branch=request.branch or "main",
            commits_indexed=stats["commits_indexed"],
            files_indexed=stats["files_processed"],
            last_indexed_commit=last_commit_hash,
        )
        # index_status save: 1 INSERT/UPSERT
        stats["db_stats"].inserts += 1

        # Calculate elapsed time
        elapsed_seconds = time.monotonic() - start_time

        return IndexRepositoryResponse(
            repository_id=repo_id,
            repository_name=repo_name,
            branch=request.branch or "main",
            commits_indexed=stats["commits_indexed"],
            files_total=stats["files_total"],
            files_processed=stats["files_processed"],
            files_skipped=stats["files_skipped"],
            files_failed=stats["files_failed"],
            files_unchanged=stats.get("files_unchanged", 0),
            files_at_head=stats.get("files_at_head", 0),
            lines_indexed=stats.get("lines_indexed", 0),
            symbols_found=stats["symbols_found"],
            references_found=stats["references_found"],
            references_resolved=stats["references_resolved"],
            files_reused=stats["files_reused"],
            symbols_reused=stats["symbols_reused"],
            references_reused=stats["references_reused"],
            errors=stats["errors"],
            elapsed_seconds=elapsed_seconds,
            db_stats=stats["db_stats"],
            oldest_commit_hash=oldest_commit["short_hash"] if oldest_commit else None,
            oldest_commit_date=(
                oldest_commit["commit_date"].strftime("%Y-%m-%d %H:%M UTC")
                if oldest_commit and oldest_commit.get("commit_date")
                else None
            ),
            newest_commit_hash=newest_commit["short_hash"] if newest_commit else None,
            newest_commit_date=(
                newest_commit["commit_date"].strftime("%Y-%m-%d %H:%M UTC")
                if newest_commit and newest_commit.get("commit_date")
                else None
            ),
        )

    async def index_incremental(
        self,
        request: IncrementalIndexRequest,
        progress_callback: ProgressCallback | None = None,
    ) -> IndexRepositoryResponse:
        """
        Incrementally index changes since last index.

        Similar to full index but only processes new commits.
        """
        start_time = time.monotonic()

        stats: dict[str, Any] = {
            "commits_indexed": 0,
            "files_total": 0,
            "files_processed": 0,
            "files_skipped": 0,
            "files_failed": 0,
            "files_at_head": 0,
            "lines_indexed": 0,
            "symbols_found": 0,
            "references_found": 0,
            "references_resolved": 0,
            "files_reused": 0,
            "symbols_reused": 0,
            "references_reused": 0,
            "errors": [],
            "db_stats": DBQueryStats(),
        }

        # Get repository
        repository = await self._repository_repo.find_by_id(request.repository_id)
        stats["db_stats"].selects += 1
        if repository is None:
            raise ValueError(f"Repository {request.repository_id} not found")

        # Find last indexed commit
        # TODO: Implement get_latest_by_repository_branch in port
        # For now, simplified - get all statuses and find latest
        all_statuses = await self._index_status_repo.list_by_repository(
            repository_id=request.repository_id
        )
        stats["db_stats"].selects += 1
        filtered_statuses = [
            s for s in all_statuses if s.branch == (request.branch or "main")
        ]
        index_status = filtered_statuses[0] if filtered_statuses else None

        last_indexed_hash = index_status.last_indexed_commit if index_status else None

        # Get new commits since last index
        current_commit = self._git_service.get_current_commit(
            repo_path=request.repository_path,
            branch=request.branch or "main",
        )

        if last_indexed_hash == current_commit:
            # No new commits, return early
            elapsed_seconds = time.monotonic() - start_time
            return IndexRepositoryResponse(
                repository_id=request.repository_id,
                repository_name=repository.name,
                branch=request.branch or "main",
                commits_indexed=0,
                files_total=0,
                files_processed=0,
                files_skipped=0,
                files_failed=0,
                symbols_found=0,
                references_found=0,
                references_resolved=0,
                files_reused=0,
                symbols_reused=0,
                references_reused=0,
                errors=[],
                elapsed_seconds=elapsed_seconds,
                db_stats=stats["db_stats"],
            )

        # Get commits since last indexed
        # list_commits returns commits from oldest to newest
        commits_data = self._git_service.list_commits(
            repo_path=request.repository_path,
            branch=request.branch or "main",
            max_count=100,  # Reasonable default
        )

        # Build content-hash cache
        content_hash_cache = await self._file_repo.get_content_hash_to_file_id_map(
            repository_id=request.repository_id
        )
        stats["db_stats"].selects += 1

        # Filter to commits that need processing
        found_last_indexed = False
        commits_to_process = []
        for commit_data in commits_data:
            if last_indexed_hash:
                if commit_data["hash"] == last_indexed_hash:
                    found_last_indexed = True
                    continue
                if not found_last_indexed:
                    continue
            commits_to_process.append(commit_data)

        # Reverse for HEAD-first indexing (newest commit processed first)
        commits_to_process = list(reversed(commits_to_process))

        # Capture commit range info for summary (after reversing: [0]=newest, [-1]=oldest)
        newest_commit = commits_to_process[0] if commits_to_process else None
        oldest_commit = commits_to_process[-1] if commits_to_process else None

        # Count total files to process (for progress)
        # HEAD commit: ALL files; other commits: only changed files
        total_files = 0
        for i, commit_data in enumerate(commits_to_process):
            if i == 0:
                # HEAD commit: count all files
                file_paths = self._git_service.list_files(
                    repo_path=request.repository_path,
                    commit_hash=commit_data["hash"],
                )
                total_files += len(file_paths)
                stats["files_at_head"] = len(file_paths)  # Track HEAD file count
            else:
                # Older commits: count only changed files
                changed = self._git_service.get_changed_files_in_commit(
                    repo_path=request.repository_path,
                    commit_hash=commit_data["hash"],
                )
                total_files += len(changed["added"]) + len(changed["modified"])
        stats["files_total"] = total_files
        stats["files_unchanged"] = 0  # Will be tracked per-commit

        # Report initial progress
        if progress_callback:
            progress_callback(
                IndexingProgress(
                    phase="files",
                    files_processed=0,
                    files_total=total_files,
                    symbols_found=0,
                    references_found=0,
                    cache_size=len(content_hash_cache),
                )
            )

        # Process each commit (HEAD first, then older commits)
        last_commit_hash: str | None = None
        for i, commit_data in enumerate(commits_to_process):
            is_head_commit = i == 0
            await self._process_commit(
                repository_id=request.repository_id,
                commit_data=commit_data,
                request=request,
                content_hash_cache=content_hash_cache,
                stats=stats,
                progress_callback=progress_callback,
                is_head_commit=is_head_commit,
            )
            stats["commits_indexed"] += 1
            last_commit_hash = commit_data["hash"]

        # Resolve references with progress
        def on_resolution_progress(p: ResolutionProgress) -> None:
            if progress_callback:
                progress_callback(
                    IndexingProgress(
                        phase="resolving",
                        files_processed=stats["files_processed"],
                        files_total=stats["files_total"],
                        symbols_found=stats["symbols_found"],
                        references_found=stats["references_found"],
                        cache_size=len(content_hash_cache),
                        refs_resolved=p.resolved,
                        refs_total=p.total,
                    )
                )
            # Track DB operations: each batch is 1 UPDATE
            stats["db_stats"].updates += 1

        # Initial count query
        stats["db_stats"].selects += 1

        resolve_request = ResolveReferencesRequest(
            repository_id=request.repository_id,
            commit_aware=True,  # Time-travel consistent: resolve to symbols at same commit
        )
        resolve_response = await self._resolve_refs_use_case.execute_with_progress(
            resolve_request,
            progress_callback=on_resolution_progress,
            batch_size=1000,
        )
        stats["references_resolved"] = resolve_response.resolved_count

        # Update index status (use last indexed hash if we processed new commits, else keep the old one)
        await self._update_index_status(
            repository_id=request.repository_id,
            branch=request.branch or "main",
            commits_indexed=stats["commits_indexed"],
            files_indexed=stats["files_processed"],
            last_indexed_commit=last_commit_hash or last_indexed_hash,
        )
        stats["db_stats"].inserts += 1

        elapsed_seconds = time.monotonic() - start_time

        return IndexRepositoryResponse(
            repository_id=request.repository_id,
            repository_name=repository.name,
            branch=request.branch or "main",
            commits_indexed=stats["commits_indexed"],
            files_total=stats["files_total"],
            files_processed=stats["files_processed"],
            files_skipped=stats["files_skipped"],
            files_failed=stats["files_failed"],
            files_unchanged=stats.get("files_unchanged", 0),
            files_at_head=stats.get("files_at_head", 0),
            lines_indexed=stats.get("lines_indexed", 0),
            symbols_found=stats["symbols_found"],
            references_found=stats["references_found"],
            references_resolved=stats["references_resolved"],
            files_reused=stats["files_reused"],
            symbols_reused=stats["symbols_reused"],
            references_reused=stats["references_reused"],
            errors=stats["errors"],
            elapsed_seconds=elapsed_seconds,
            db_stats=stats["db_stats"],
            oldest_commit_hash=oldest_commit["short_hash"] if oldest_commit else None,
            oldest_commit_date=(
                oldest_commit["commit_date"].strftime("%Y-%m-%d %H:%M UTC")
                if oldest_commit and oldest_commit.get("commit_date")
                else None
            ),
            newest_commit_hash=newest_commit["short_hash"] if newest_commit else None,
            newest_commit_date=(
                newest_commit["commit_date"].strftime("%Y-%m-%d %H:%M UTC")
                if newest_commit and newest_commit.get("commit_date")
                else None
            ),
        )

    async def _process_commit(
        self,
        repository_id: int,
        commit_data: dict,
        request: IndexRepositoryRequest | IncrementalIndexRequest,
        content_hash_cache: dict[str, int],
        stats: dict,
        progress_callback: ProgressCallback | None = None,
        is_head_commit: bool = False,
    ) -> None:
        """Process a single commit.

        Args:
            repository_id: Database ID of the repository
            commit_data: Git commit information dict
            request: The indexing request
            content_hash_cache: Cache for content-hash optimization
            stats: Statistics dict to update
            progress_callback: Optional progress callback
            is_head_commit: If True, process ALL files (not just changed ones).
                           This ensures complete coverage at HEAD for time-travel.
        """
        from datetime import UTC, datetime

        commit_hash_str = commit_data["hash"]

        # Check if commit already exists (for re-indexing scenarios)
        existing_commit = await self._commit_repo.find_by_hash(
            repository_id=repository_id,
            commit_hash=commit_hash_str,
        )
        stats["db_stats"].selects += 1

        if existing_commit is not None:
            # Commit already indexed, skip creating but still link to current branch
            commit_id = existing_commit.id
            assert commit_id is not None
            # Still need to process files (they might have been partially indexed)
        else:
            # Save new commit to database
            # Note: Commit entity only stores hash and dates, not author/message

            # Get datetime values from commit data
            # GitPython returns timezone-aware datetimes, DB expects naive UTC
            author_date = commit_data.get("author_date")
            commit_date = commit_data.get("commit_date")

            # Handle both datetime objects (from GitPython) and strings (from tests)
            if isinstance(author_date, str):
                author_date = datetime.fromisoformat(author_date.replace("Z", "+00:00"))
            if isinstance(commit_date, str):
                commit_date = datetime.fromisoformat(commit_date.replace("Z", "+00:00"))

            # If not provided, use current time
            if author_date is None:
                author_date = datetime.now(UTC)
            if commit_date is None:
                commit_date = datetime.now(UTC)

            # Convert to naive UTC for database storage
            if author_date.tzinfo is not None:
                author_date = author_date.astimezone(UTC).replace(tzinfo=None)
            if commit_date.tzinfo is not None:
                commit_date = commit_date.astimezone(UTC).replace(tzinfo=None)

            commit = Commit(
                id=None,
                repository_id=repository_id,
                commit_hash=CommitHash(commit_hash_str),
                author_date=author_date,
                commit_date=commit_date,
            )
            db_commit = await self._commit_repo.save(commit)
            stats["db_stats"].inserts += 1
            commit_id = db_commit.id
            assert commit_id is not None, "Commit must have an ID after save"

        # Link commit to the current branch being indexed
        branch = request.branch or "main"
        await self._commit_repo.link_commit_to_branch(
            repository_id=repository_id,
            commit_id=commit_id,
            branch=branch,
        )
        stats["db_stats"].inserts += 1

        repo_path = getattr(request, "repository_path", Path("."))

        if is_head_commit:
            # HEAD commit: process ALL files to ensure complete coverage
            # This is essential for time-travel queries to work correctly
            files_to_process = self._git_service.list_files(
                repo_path=repo_path,
                commit_hash=commit_data["hash"],
            )
            # No unchanged files for HEAD - we process everything
        else:
            # Older commits: delta indexing - only process changed files
            # Unchanged files already have records from HEAD or later commits
            changed = self._git_service.get_changed_files_in_commit(
                repo_path=repo_path,
                commit_hash=commit_data["hash"],
            )

            # Only process added and modified files (deleted files don't need processing)
            files_to_process = changed["added"] + changed["modified"]

            # Track unchanged files (all files minus changed files)
            all_files = self._git_service.list_files(
                repo_path=repo_path,
                commit_hash=commit_data["hash"],
            )
            unchanged_count = (
                len(all_files) - len(files_to_process) - len(changed["deleted"])
            )
            stats["files_unchanged"] = stats.get("files_unchanged", 0) + max(
                0, unchanged_count
            )

        # Process each file
        for file_path_str in files_to_process:
            await self._process_file(
                repository_id=repository_id,
                commit_id=commit_id,
                file_path_str=file_path_str,
                commit_hash=commit_data["hash"],
                repo_path=repo_path,
                content_hash_cache=content_hash_cache,
                request=request,
                stats=stats,
            )

            # Report progress after each file
            if progress_callback:
                progress_callback(
                    IndexingProgress(
                        phase="files",
                        files_processed=stats["files_processed"],
                        files_total=stats["files_total"],
                        symbols_found=stats["symbols_found"],
                        references_found=stats["references_found"],
                        cache_size=len(content_hash_cache),
                    )
                )

    async def _process_file(
        self,
        repository_id: int,
        commit_id: int,
        file_path_str: str,
        commit_hash: str,
        repo_path: Path,
        content_hash_cache: dict[str, int],
        request: IndexRepositoryRequest | IncrementalIndexRequest,
        stats: dict,
    ) -> None:
        """Process a single file."""
        try:
            # Get file content
            content = self._git_service.get_file_content(
                repo_path=repo_path,
                commit_hash=commit_hash,
                file_path=file_path_str,
            )

            # Calculate content hash
            content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()

            # Detect language (simplified - would use LanguageDetector)
            language = self._detect_language(file_path_str)

            # Create file record
            file_entity = File(
                id=None,
                repository_id=repository_id,
                commit_id=commit_id,
                path=file_path_str,
                content_hash=content_hash,
                size_bytes=len(content.encode("utf-8")),
                language=language,
                line_count=content.count("\n") + 1,
            )
            db_file = await self._file_repo.save(file_entity)
            stats["db_stats"].inserts += 1
            file_id = db_file.id
            assert file_id is not None, "File must have an ID after save"

            # Try content-hash optimization
            optimize_request = OptimizeFileIndexingRequest(
                target_file_id=file_id,
                target_commit_id=commit_id,
                target_repository_id=repository_id,
                content_hash=content_hash,
                content_hash_cache=content_hash_cache,
            )
            optimization_result = await self._optimize_use_case.execute(
                optimize_request
            )

            if optimization_result.optimization_applied:
                # Reused symbols/references from donor file
                stats["files_reused"] += 1
                stats["files_processed"] += 1
                stats["symbols_reused"] += optimization_result.symbols_copied
                stats["references_reused"] += optimization_result.references_copied
                stats["symbols_found"] += optimization_result.symbols_copied
                stats["references_found"] += optimization_result.references_copied
                # copy_symbols_to_file: 1 SELECT + N INSERTs
                # copy_references_to_file: 1 SELECT + N INSERTs
                stats["db_stats"].selects += 2
                stats["db_stats"].inserts += (
                    optimization_result.symbols_copied
                    + optimization_result.references_copied
                )
                # Track lines indexed
                stats["lines_indexed"] = (
                    stats.get("lines_indexed", 0) + file_entity.line_count
                )
                # Add to cache for future files
                content_hash_cache[content_hash] = file_id
            else:
                # Parse file and extract symbols/references
                if language and self._parser_service.supports_language(language):
                    symbols_data, references_data = (
                        await self._parser_service.parse_file(
                            content=content,
                            language=language,
                            file_path=file_path_str,
                        )
                    )

                    # Save symbols (parse_file returns dicts, not Symbol objects)
                    for symbol_data in symbols_data:
                        # Create Symbol from dict data
                        symbol = Symbol(
                            id=None,
                            file_id=file_id,
                            repository_id=repository_id,
                            commit_id=commit_id,
                            name=symbol_data["name"],
                            kind=SymbolKind(symbol_data["kind"]),
                            start_line=symbol_data["start_line"],
                            start_column=symbol_data["start_column"],
                            end_line=symbol_data["end_line"],
                            end_column=symbol_data["end_column"],
                            parent_symbol_id=symbol_data.get("parent_symbol_id"),
                            signature=symbol_data.get("signature"),
                            metadata=symbol_data.get("metadata", {}),
                        )
                        await self._symbol_repo.save(symbol)
                        stats["db_stats"].inserts += 1
                        stats["symbols_found"] += 1

                    # Save references
                    for ref_data in references_data:
                        # Parsers use "text" and "type", not "reference_text" and "reference_type"
                        reference_text = ref_data.get("text") or ref_data.get(
                            "reference_text", ""
                        )
                        reference_type = ref_data.get("type") or ref_data.get(
                            "reference_type", "usage"
                        )
                        source_column = ref_data["source_column"]

                        # Calculate source_end_column if not provided
                        source_end_column = ref_data.get(
                            "source_end_column",
                            source_column + len(reference_text),
                        )

                        reference = Reference(
                            id=None,
                            repository_id=repository_id,
                            commit_id=commit_id,
                            source_file_id=file_id,
                            source_line=ref_data["source_line"],
                            source_column=source_column,
                            source_end_column=source_end_column,
                            reference_text=reference_text,
                            reference_type=ReferenceType(reference_type),
                            target_symbol_id=None,  # Will be resolved later
                        )
                        await self._reference_repo.save(reference)
                        stats["db_stats"].inserts += 1
                        stats["references_found"] += 1

                    # Add to cache
                    content_hash_cache[content_hash] = file_id
                    stats["files_processed"] += 1
                    # Track lines indexed
                    stats["lines_indexed"] = (
                        stats.get("lines_indexed", 0) + file_entity.line_count
                    )
                else:
                    stats["files_skipped"] += 1

        except Exception as e:
            stats["files_failed"] += 1
            stats["errors"].append(f"Failed to process {file_path_str}: {str(e)}")

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

    def _detect_language(self, file_path: str) -> str | None:
        """Detect language from file extension."""
        ext_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".java": "java",
            ".c": "c",
            ".h": "c",
        }
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return None

"""
Default implementation of IndexingOrchestratorPort.

This orchestrator coordinates the indexing workflow, delegating to
specialized use cases and services while keeping the orchestration
logic separate from CLI concerns.
"""

import hashlib
import time
from pathlib import Path
from typing import Any

from inxr2.domain.entities import (
    Commit,
    File,
    IndexStatus,
    Reference,
    Symbol,
)
from inxr2.domain.value_objects import CommitHash

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
    IncrementalIndexRequest,
    IndexRepositoryRequest,
    IndexRepositoryResponse,
)
from .resolve_references import ResolveReferencesRequest, ResolveReferencesUseCase


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
        self, request: IndexRepositoryRequest
    ) -> IndexRepositoryResponse:
        """
        Index a repository with specified strategy.

        This is the main entry point for repository indexing.
        """
        start_time = time.monotonic()

        # Statistics tracking
        stats: dict[str, Any] = {
            "commits_indexed": 0,
            "files_total": 0,
            "files_processed": 0,
            "files_skipped": 0,
            "files_failed": 0,
            "symbols_found": 0,
            "references_found": 0,
            "references_resolved": 0,
            "files_reused": 0,
            "symbols_reused": 0,
            "references_reused": 0,
            "errors": [],
        }

        # Step 1: Prepare repository
        repo_name = request.repository_path.name
        repository, created = await self._repository_repo.get_or_create(
            name=repo_name,
            url=str(request.repository_path),
            default_branch=request.branch or "main",
        )
        repo_id = repository.id
        assert repo_id is not None, "Repository must have an ID after save"

        # Step 2: Get commits to process
        commits_data = self._git_service.get_commits(
            repo_path=request.repository_path,
            branch=request.branch or "main",
            max_count=request.max_history,
            since_days=request.since_days,
            oldest_first=True,  # Process oldest first for time-travel
        )

        # Step 3: Build content-hash cache for optimization
        content_hash_cache = await self._file_repo.get_content_hash_to_file_id_map(
            repository_id=repo_id
        )

        # Step 4: Process each commit
        last_commit_hash: str | None = None
        for commit_data in commits_data:
            await self._process_commit(
                repository_id=repo_id,
                commit_data=commit_data,
                request=request,
                content_hash_cache=content_hash_cache,
                stats=stats,
            )
            stats["commits_indexed"] += 1
            last_commit_hash = commit_data["hash"]

        # Step 5: Resolve references
        resolve_request = ResolveReferencesRequest(
            repository_id=repo_id,
            commit_aware=False,  # Cross-commit resolution by default
        )
        resolve_response = await self._resolve_refs_use_case.execute(resolve_request)
        stats["references_resolved"] = resolve_response.resolved_count

        # Step 6: Update index status
        await self._update_index_status(
            repository_id=repo_id,
            branch=request.branch or "main",
            commits_indexed=stats["commits_indexed"],
            files_indexed=stats["files_processed"],
            last_indexed_commit=last_commit_hash,
        )

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
            symbols_found=stats["symbols_found"],
            references_found=stats["references_found"],
            references_resolved=stats["references_resolved"],
            files_reused=stats["files_reused"],
            symbols_reused=stats["symbols_reused"],
            references_reused=stats["references_reused"],
            errors=stats["errors"],
            elapsed_seconds=elapsed_seconds,
        )

    async def index_incremental(
        self, request: IncrementalIndexRequest
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
            "symbols_found": 0,
            "references_found": 0,
            "references_resolved": 0,
            "files_reused": 0,
            "symbols_reused": 0,
            "references_reused": 0,
            "errors": [],
        }

        # Get repository
        repository = await self._repository_repo.find_by_id(request.repository_id)
        if repository is None:
            raise ValueError(f"Repository {request.repository_id} not found")

        # Find last indexed commit
        # TODO: Implement get_latest_by_repository_branch in port
        # For now, simplified - get all statuses and find latest
        all_statuses = await self._index_status_repo.list_by_repository(
            repository_id=request.repository_id
        )
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
            )

        # Get commits since last indexed
        # (This would require git log filtering - simplified for now)
        commits_data = self._git_service.get_commits(
            repo_path=request.repository_path,
            branch=request.branch or "main",
            max_count=100,  # Reasonable default
            oldest_first=True,
        )

        # Build content-hash cache
        content_hash_cache = await self._file_repo.get_content_hash_to_file_id_map(
            repository_id=request.repository_id
        )

        # Process each new commit
        found_last_indexed = False
        last_commit_hash: str | None = None
        for commit_data in commits_data:
            # Skip commits until we pass the last indexed commit
            if last_indexed_hash:
                if commit_data["hash"] == last_indexed_hash:
                    found_last_indexed = True
                    continue  # Skip this exact commit (already indexed)
                if not found_last_indexed:
                    continue  # Skip all commits before the last indexed

            await self._process_commit(
                repository_id=request.repository_id,
                commit_data=commit_data,
                request=request,
                content_hash_cache=content_hash_cache,
                stats=stats,
            )
            stats["commits_indexed"] += 1
            last_commit_hash = commit_data["hash"]

        # Resolve references
        resolve_request = ResolveReferencesRequest(
            repository_id=request.repository_id,
            commit_aware=False,
        )
        resolve_response = await self._resolve_refs_use_case.execute(resolve_request)
        stats["references_resolved"] = resolve_response.resolved_count

        # Update index status (use last indexed hash if we processed new commits, else keep the old one)
        await self._update_index_status(
            repository_id=request.repository_id,
            branch=request.branch or "main",
            commits_indexed=stats["commits_indexed"],
            files_indexed=stats["files_processed"],
            last_indexed_commit=last_commit_hash or last_indexed_hash,
        )

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
            symbols_found=stats["symbols_found"],
            references_found=stats["references_found"],
            references_resolved=stats["references_resolved"],
            files_reused=stats["files_reused"],
            symbols_reused=stats["symbols_reused"],
            references_reused=stats["references_reused"],
            errors=stats["errors"],
            elapsed_seconds=elapsed_seconds,
        )

    async def _process_commit(
        self,
        repository_id: int,
        commit_data: dict,
        request: IndexRepositoryRequest | IncrementalIndexRequest,
        content_hash_cache: dict[str, int],
        stats: dict,
    ) -> None:
        """Process a single commit."""
        # Save commit to database
        # Note: Commit entity only stores hash and dates, not author/message
        from datetime import UTC, datetime

        commit_date = datetime.fromisoformat(
            commit_data.get("timestamp", datetime.now(UTC).isoformat()).replace(
                "Z", "+00:00"
            )
        )

        commit = Commit(
            id=None,
            repository_id=repository_id,
            commit_hash=CommitHash(commit_data["hash"]),
            author_date=commit_date,
            commit_date=commit_date,
        )
        db_commit = await self._commit_repo.save(commit)
        commit_id = db_commit.id
        assert commit_id is not None, "Commit must have an ID after save"

        # Get files in this commit
        repo_path = getattr(request, "repository_path", Path("."))
        file_paths = self._git_service.get_files_in_commit(
            repo_path=repo_path,
            commit_hash=commit_data["hash"],
        )

        stats["files_total"] += len(file_paths)

        # Process each file
        for file_path_str in file_paths:
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
                stats["symbols_reused"] += optimization_result.symbols_copied
                stats["references_reused"] += optimization_result.references_copied
                stats["symbols_found"] += optimization_result.symbols_copied
                stats["references_found"] += optimization_result.references_copied
                # Add to cache for future files
                content_hash_cache[content_hash] = file_id
            else:
                # Parse file and extract symbols/references
                if language and self._parser_service.supports_language(language):
                    symbols, references_data = await self._parser_service.parse_file(
                        file_path=Path(file_path_str),
                        content=content,
                        language=language,
                    )

                    # Save symbols
                    for symbol in symbols:
                        # Update symbol with correct IDs
                        updated_symbol = Symbol(
                            id=None,
                            file_id=file_id,
                            repository_id=repository_id,
                            commit_id=commit_id,
                            name=symbol.name,
                            kind=symbol.kind,
                            start_line=symbol.start_line,
                            start_column=symbol.start_column,
                            end_line=symbol.end_line,
                            end_column=symbol.end_column,
                            parent_symbol_id=symbol.parent_symbol_id,
                            signature=symbol.signature,
                            metadata=symbol.metadata,
                        )
                        await self._symbol_repo.save(updated_symbol)
                        stats["symbols_found"] += 1

                    # Save references
                    for ref_data in references_data:
                        reference = Reference(
                            id=None,
                            repository_id=repository_id,
                            commit_id=commit_id,
                            source_file_id=file_id,
                            source_line=ref_data["source_line"],
                            source_column=ref_data["source_column"],
                            source_end_column=ref_data["source_end_column"],
                            reference_text=ref_data["reference_text"],
                            reference_type=ref_data["reference_type"],
                            target_symbol_id=None,  # Will be resolved later
                        )
                        await self._reference_repo.save(reference)
                        stats["references_found"] += 1

                    # Add to cache
                    content_hash_cache[content_hash] = file_id
                else:
                    stats["files_skipped"] += 1

            stats["files_processed"] += 1

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

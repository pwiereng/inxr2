"""
Process commit use case.

Handles processing a single commit during indexing: saving the commit record,
linking to branch, indexing commit message, and delegating file processing
to ProcessFileUseCase.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from inxr2.domain.entities import Commit, TextContent
from inxr2.domain.value_objects import CommitHash, TextSearchSourceType

from ...ports.repositories import CommitRepositoryPort, TextContentRepositoryPort
from ...ports.services import CommitInfo, GitServicePort
from .process_file import ProcessFileRequest, ProcessFileResult, ProcessFileUseCase


@dataclass
class ProcessCommitRequest:
    """Request to process a single commit during indexing."""

    repository_id: int
    commit_data: CommitInfo
    repo_path: Path
    branch: str
    content_hash_cache: dict[str, int]
    is_head_commit: bool


@dataclass
class ProcessCommitResult:
    """Result of processing a single commit."""

    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    files_unchanged: int = 0
    symbols_found: int = 0
    references_found: int = 0
    files_reused: int = 0
    symbols_reused: int = 0
    references_reused: int = 0
    lines_indexed: int = 0
    comments_indexed: int = 0
    docstrings_indexed: int = 0
    commit_messages_indexed: int = 0
    non_code_files_indexed: int = 0
    errors: list[str] = field(default_factory=list)
    db_inserts: int = 0
    db_selects: int = 0


# Type alias for per-file progress callback
FileProgressCallback = Callable[[ProcessCommitResult], None]


class ProcessCommitUseCase:
    """
    Use case for processing a single commit during indexing.

    Handles:
    - Saving commit to database (or reusing existing)
    - Linking commit to branch
    - Indexing commit message as text content
    - Determining files to process (all for HEAD, delta for older)
    - Delegating file processing to ProcessFileUseCase
    """

    def __init__(
        self,
        commit_repo: CommitRepositoryPort,
        git_service: GitServicePort,
        text_content_repo: TextContentRepositoryPort,
        process_file_use_case: ProcessFileUseCase,
    ) -> None:
        self._commit_repo = commit_repo
        self._git_service = git_service
        self._text_content_repo = text_content_repo
        self._process_file_use_case = process_file_use_case

    async def execute(
        self,
        request: ProcessCommitRequest,
        progress_callback: FileProgressCallback | None = None,
    ) -> ProcessCommitResult:
        """Process a single commit: save, link to branch, process files."""
        from datetime import UTC, datetime

        result = ProcessCommitResult()
        commit_hash_str = request.commit_data.hash

        # Check if commit already exists
        existing_commit = await self._commit_repo.find_by_hash(
            repository_id=request.repository_id,
            commit_hash=commit_hash_str,
        )
        result.db_selects += 1

        if existing_commit is not None:
            commit_id = existing_commit.id
            assert commit_id is not None
        else:
            # Save new commit to database
            author_date: datetime | None = request.commit_data.author_date
            commit_date: datetime | None = request.commit_data.commit_date

            if isinstance(author_date, str):
                author_date = datetime.fromisoformat(author_date.replace("Z", "+00:00"))
            if isinstance(commit_date, str):
                commit_date = datetime.fromisoformat(commit_date.replace("Z", "+00:00"))

            if author_date is None:
                author_date = datetime.now(UTC)
            if commit_date is None:
                commit_date = datetime.now(UTC)

            if author_date.tzinfo is not None:
                author_date = author_date.astimezone(UTC).replace(tzinfo=None)
            if commit_date.tzinfo is not None:
                commit_date = commit_date.astimezone(UTC).replace(tzinfo=None)

            commit = Commit(
                id=None,
                repository_id=request.repository_id,
                commit_hash=CommitHash(commit_hash_str),
                author_date=author_date,
                commit_date=commit_date,
            )
            db_commit = await self._commit_repo.save(commit)
            result.db_inserts += 1
            commit_id = db_commit.id
            assert commit_id is not None, "Commit must have an ID after save"

        # Link commit to branch
        await self._commit_repo.link_commit_to_branch(
            repository_id=request.repository_id,
            commit_id=commit_id,
            branch=request.branch,
        )
        result.db_inserts += 1

        # Index commit message (skip if commit already exists)
        if existing_commit is None:
            await self._index_commit_message(
                repository_id=request.repository_id,
                commit_id=commit_id,
                commit_data=request.commit_data,
                result=result,
            )

        # Determine files to process
        if request.is_head_commit:
            files_to_process = self._git_service.list_files(
                repo_path=request.repo_path,
                commit_hash=request.commit_data.hash,
            )
        else:
            changed = self._git_service.get_changed_files_in_commit(
                repo_path=request.repo_path,
                commit_hash=request.commit_data.hash,
            )
            files_to_process = changed.added + changed.modified

            # Track unchanged files
            all_files = self._git_service.list_files(
                repo_path=request.repo_path,
                commit_hash=request.commit_data.hash,
            )
            unchanged_count = (
                len(all_files) - len(files_to_process) - len(changed.deleted)
            )
            result.files_unchanged = max(0, unchanged_count)

        # Process each file
        for file_path_str in files_to_process:
            file_request = ProcessFileRequest(
                repository_id=request.repository_id,
                commit_id=commit_id,
                file_path=file_path_str,
                commit_hash=request.commit_data.hash,
                repo_path=request.repo_path,
                content_hash_cache=request.content_hash_cache,
            )
            file_result = await self._process_file_use_case.execute(file_request)
            self._aggregate_file_result(result, file_result)

            if progress_callback:
                progress_callback(result)

        return result

    def _aggregate_file_result(
        self, result: ProcessCommitResult, file_result: ProcessFileResult
    ) -> None:
        """Aggregate a file result into the commit result."""
        if file_result.processed:
            result.files_processed += 1
        if file_result.skipped:
            result.files_skipped += 1
        if file_result.failed:
            result.files_failed += 1
        if file_result.reused:
            result.files_reused += 1
        result.symbols_found += file_result.symbols_found
        result.references_found += file_result.references_found
        result.symbols_reused += file_result.symbols_reused
        result.references_reused += file_result.references_reused
        result.lines_indexed += file_result.lines_indexed
        result.comments_indexed += file_result.comments_indexed
        result.docstrings_indexed += file_result.docstrings_indexed
        if file_result.non_code_file_indexed:
            result.non_code_files_indexed += 1
        if file_result.error:
            result.errors.append(file_result.error)
        result.db_inserts += file_result.db_inserts
        result.db_selects += file_result.db_selects

    async def _index_commit_message(
        self,
        repository_id: int,
        commit_id: int,
        commit_data: CommitInfo,
        result: ProcessCommitResult,
    ) -> None:
        """Index commit message as searchable text content."""
        try:
            commit_message = commit_data.message.strip()
            if not commit_message:
                return

            text_content = TextContent(
                id=None,
                repository_id=repository_id,
                commit_id=commit_id,
                source_type=TextSearchSourceType.COMMIT_MESSAGE.value,
                source_file_id=None,
                source_line=None,
                source_end_line=None,
                content=commit_message,
                language=None,
                content_type="commit_message",
            )
            await self._text_content_repo.save(text_content)
            result.db_inserts += 1
            result.commit_messages_indexed += 1

        except Exception as e:
            result.errors.append(
                f"Failed to index commit message for commit {commit_data.hash}: {e}"
            )

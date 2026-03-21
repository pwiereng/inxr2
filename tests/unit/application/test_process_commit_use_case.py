"""Tests for ProcessCommitUseCase."""

from datetime import datetime
from pathlib import Path

import pytest

from inxr2.application.ports.services import CommitInfo, ParserServicePort
from inxr2.application.use_cases.indexing.process_commit import (
    ProcessCommitRequest,
    ProcessCommitUseCase,
)
from inxr2.application.use_cases.indexing.process_file import ProcessFileUseCase
from inxr2.domain.constants import DatabaseLimits
from tests.fixtures.test_doubles import (
    FakeGitService,
    FakePlaintextParser,
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
    InMemoryTextContentRepository,
)


class FakeParserService(ParserServicePort):
    """Fake parser service for testing."""

    def supports_language(self, language: str) -> bool:
        return language in ["python", "typescript", "java"]

    async def parse_file(
        self, content: str, language: str, file_path: str
    ) -> tuple[list[dict], list[dict]]:
        file_name = Path(file_path).name
        symbols = [
            {
                "name": f"function_in_{file_name}",
                "kind": "function",
                "start_line": 1,
                "start_column": 0,
                "end_line": 5,
                "end_column": 0,
            }
        ]
        references = [
            {
                "text": "print",
                "type": "call",
                "source_line": 2,
                "source_column": 0,
            }
        ]
        return symbols, references

    async def extract_comments(
        self, content: str, language: str, file_path: str
    ) -> list[dict]:
        return [
            {
                "content": f"Comment in {Path(file_path).name}",
                "content_type": "single_line_comment",
                "source_line": 1,
            }
        ]


@pytest.fixture
def git_service() -> FakeGitService:
    return FakeGitService()


@pytest.fixture
def commit_repo() -> InMemoryCommitRepository:
    return InMemoryCommitRepository()


@pytest.fixture
def file_repo() -> InMemoryFileRepository:
    return InMemoryFileRepository()


@pytest.fixture
def symbol_repo() -> InMemorySymbolRepository:
    return InMemorySymbolRepository()


@pytest.fixture
def reference_repo(
    symbol_repo: InMemorySymbolRepository,
) -> InMemoryReferenceRepository:
    return InMemoryReferenceRepository(symbol_repo=symbol_repo)


@pytest.fixture
def text_content_repo() -> InMemoryTextContentRepository:
    return InMemoryTextContentRepository()


@pytest.fixture
def parser_service() -> FakeParserService:
    return FakeParserService()


@pytest.fixture
def use_case(
    commit_repo: InMemoryCommitRepository,
    git_service: FakeGitService,
    text_content_repo: InMemoryTextContentRepository,
    file_repo: InMemoryFileRepository,
    symbol_repo: InMemorySymbolRepository,
    reference_repo: InMemoryReferenceRepository,
    parser_service: FakeParserService,
) -> ProcessCommitUseCase:
    process_file = ProcessFileUseCase(
        git_service=git_service,
        file_repo=file_repo,
        symbol_repo=symbol_repo,
        reference_repo=reference_repo,
        text_content_repo=text_content_repo,
        parser_service=parser_service,
        plaintext_parser=FakePlaintextParser(),
    )
    return ProcessCommitUseCase(
        commit_repo=commit_repo,
        file_repo=file_repo,
        git_service=git_service,
        text_content_repo=text_content_repo,
        process_file_use_case=process_file,
    )


def _make_commit(
    hash: str = "abc123",
    message: str = "Test commit",
    date: datetime | None = None,
) -> CommitInfo:
    d = date or datetime(2024, 1, 1, 0, 0, 0)
    return CommitInfo(
        hash=hash,
        short_hash=hash[:7],
        author_name="Test User",
        author_email="test@example.com",
        author_date=d,
        committer_name="Test User",
        committer_email="test@example.com",
        commit_date=d,
        message=message,
        parent_hashes=[],
    )


class TestProcessCommitUseCase:
    """Tests for ProcessCommitUseCase."""

    @pytest.mark.asyncio
    async def test_new_commit_saved_and_linked(
        self,
        use_case: ProcessCommitUseCase,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Test that a new commit is saved to DB and linked to branch."""
        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )

        result = await use_case.execute(request)

        # Commit should be saved
        commits = await commit_repo.list_by_repository(repository_id=1)
        assert len(commits) == 1
        assert commits[0].commit_hash.value == "abc123"

        # Commit should be linked to branch
        assert commits[0].id is not None
        branches = await commit_repo.get_branches_for_commit(commits[0].id)
        assert "main" in branches

        # Result should have processed files
        assert result.files_processed > 0

    @pytest.mark.asyncio
    async def test_existing_commit_reused(
        self,
        use_case: ProcessCommitUseCase,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Test that existing commit is reused, not duplicated."""
        commit_data = _make_commit()

        # Process once
        request1 = ProcessCommitRequest(
            repository_id=1,
            commit_data=commit_data,
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )
        await use_case.execute(request1)

        commits_after_first = await commit_repo.list_by_repository(repository_id=1)
        assert len(commits_after_first) == 1

        # Process again (same commit, different branch)
        request2 = ProcessCommitRequest(
            repository_id=1,
            commit_data=commit_data,
            repo_path=Path("/repos/test-repo"),
            branch="feature",
        )
        await use_case.execute(request2)

        # Still only 1 commit, but linked to both branches
        commits_after_second = await commit_repo.list_by_repository(repository_id=1)
        assert len(commits_after_second) == 1

        assert commits_after_second[0].id is not None
        branches = await commit_repo.get_branches_for_commit(commits_after_second[0].id)
        assert "main" in branches
        assert "feature" in branches

    @pytest.mark.asyncio
    async def test_new_commit_processes_all_files(
        self,
        use_case: ProcessCommitUseCase,
        git_service: FakeGitService,
    ) -> None:
        """Test that every new commit processes ALL files (full snapshot)."""
        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )

        result = await use_case.execute(request)

        # Full snapshot: processes all files in commit
        all_files = git_service.list_files(
            repo_path=Path("/repos/test-repo"),
            commit_hash="abc123",
        )
        assert (
            result.files_processed + result.files_skipped + result.files_failed
            == len(all_files)
        )

    @pytest.mark.asyncio
    async def test_existing_commit_skips_file_processing(
        self,
        use_case: ProcessCommitUseCase,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Test that existing commit links branch but skips file processing."""
        commit_data = _make_commit()

        # Process once on main
        request1 = ProcessCommitRequest(
            repository_id=1,
            commit_data=commit_data,
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )
        result1 = await use_case.execute(request1)
        assert result1.files_processed > 0

        # Process again on feature — should skip files entirely
        request2 = ProcessCommitRequest(
            repository_id=1,
            commit_data=commit_data,
            repo_path=Path("/repos/test-repo"),
            branch="feature",
        )
        result2 = await use_case.execute(request2)
        assert (
            result2.files_processed == 0
        ), "Existing commit should skip file processing"

    @pytest.mark.asyncio
    async def test_commit_message_always_indexed(
        self,
        use_case: ProcessCommitUseCase,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Test that commit message is always indexed as text content."""
        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(message="Add new feature"),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )

        result = await use_case.execute(request)

        assert result.commit_messages_indexed == 1
        all_text = text_content_repo.get_all()
        commit_msgs = [tc for tc in all_text if tc.source_type == "commit_message"]
        assert len(commit_msgs) == 1
        assert commit_msgs[0].content == "Add new feature"

    @pytest.mark.asyncio
    async def test_result_aggregates_file_results(
        self,
        use_case: ProcessCommitUseCase,
    ) -> None:
        """Test that result correctly aggregates file-level results."""
        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )

        result = await use_case.execute(request)

        # Should have aggregate stats from all files
        total_files = (
            result.files_processed + result.files_skipped + result.files_failed
        )
        assert total_files > 0
        assert result.symbols_found >= 0
        assert result.references_found >= 0

    @pytest.mark.asyncio
    async def test_existing_commit_message_not_duplicated(
        self,
        use_case: ProcessCommitUseCase,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Test that re-processing an existing commit doesn't duplicate its message."""
        commit_data = _make_commit(message="Test message")

        # Process twice
        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=commit_data,
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )
        await use_case.execute(request)
        await use_case.execute(request)

        all_text = text_content_repo.get_all()
        commit_msgs = [tc for tc in all_text if tc.source_type == "commit_message"]
        assert len(commit_msgs) == 1, "Commit message should not be duplicated"

    @pytest.mark.asyncio
    async def test_oversized_commit_message_is_truncated(
        self,
        use_case: ProcessCommitUseCase,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Commit message exceeding tsvector limit should be truncated, not fail."""
        large_message = "word " * (DatabaseLimits.MAX_TSVECTOR_BYTES // 2)
        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(message=large_message),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )

        result = await use_case.execute(request)

        assert result.commit_messages_indexed == 1
        all_text = text_content_repo.get_all()
        commit_msgs = [tc for tc in all_text if tc.source_type == "commit_message"]
        assert len(commit_msgs) == 1
        assert (
            len(commit_msgs[0].content.encode("utf-8"))
            <= DatabaseLimits.MAX_TSVECTOR_BYTES
        )

    @pytest.mark.asyncio
    async def test_minified_files_always_skipped(
        self,
        use_case: ProcessCommitUseCase,
        git_service: FakeGitService,
        symbol_repo: InMemorySymbolRepository,
    ) -> None:
        """Minified/bundled files are always skipped regardless of exclude_paths."""
        git_service.files_in_commit["abc123"] = [
            "src/main.py",
            "lib/jquery.min.js",
            "static/app.bundle.js",
        ]

        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )

        result = await use_case.execute(request)

        # Only src/main.py processed; minified/bundled always skipped
        assert result.files_processed == 1
        assert result.files_skipped == 2

    @pytest.mark.asyncio
    async def test_exclude_paths_skips_matching_directories(
        self,
        use_case: ProcessCommitUseCase,
        git_service: FakeGitService,
        symbol_repo: InMemorySymbolRepository,
    ) -> None:
        """Files in excluded directories are skipped when exclude_paths is set."""
        git_service.files_in_commit["abc123"] = [
            "src/main.py",
            "node_modules/express/index.js",
            "vendor/jquery.js",
            "dist/bundle.js",
        ]

        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
            exclude_paths=("node_modules", "vendor", "dist"),
        )

        result = await use_case.execute(request)

        # Only src/main.py should be processed; the other 3 match exclude_paths
        assert result.files_processed == 1
        assert result.files_skipped == 3

    @pytest.mark.asyncio
    async def test_without_exclude_paths_vendor_dirs_are_indexed(
        self,
        use_case: ProcessCommitUseCase,
        git_service: FakeGitService,
        symbol_repo: InMemorySymbolRepository,
    ) -> None:
        """Without exclude_paths, vendor/dist directories are indexed normally."""
        git_service.files_in_commit["abc123"] = [
            "src/main.py",
            "vendor/jquery.js",
            "dist/bundle.js",
        ]

        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
            # no exclude_paths — vendor/dist are first-party committed code
        )

        result = await use_case.execute(request)

        # All 3 files should be indexed (no exclude_paths set, minified filter doesn't match)
        assert result.files_skipped == 0
        assert result.files_processed == 3

    @pytest.mark.asyncio
    async def test_normal_files_not_skipped(
        self,
        use_case: ProcessCommitUseCase,
        git_service: FakeGitService,
    ) -> None:
        """Normal source files should not be affected by vendor filtering."""
        git_service.files_in_commit["abc123"] = [
            "src/main.py",
            "src/utils.ts",
            "lib/helpers.js",
        ]

        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )

        result = await use_case.execute(request)

        # All files should be processed (none skipped by vendor filter)
        total = result.files_processed + result.files_skipped + result.files_failed
        assert total == 3
        assert result.files_skipped == 0

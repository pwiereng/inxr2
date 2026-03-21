"""Tests for rename detection in ProcessCommitUseCase."""

from datetime import datetime
from pathlib import Path

import pytest

from inxr2.application.ports.services import (
    CommitInfo,
    ParsedComment,
    ParsedReference,
    ParsedSymbol,
    ParserServicePort,
    RenameInfo,
)
from inxr2.application.use_cases.indexing.process_commit import (
    ProcessCommitRequest,
    ProcessCommitUseCase,
)
from inxr2.application.use_cases.indexing.process_file import ProcessFileUseCase
from tests.fixtures.test_doubles import (
    FakeGitService,
    FakePlaintextParser,
    InMemoryCommitRepository,
    InMemoryFileRenameRepository,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
    InMemoryTextContentRepository,
)


class FakeParserService(ParserServicePort):
    """Minimal fake parser service for rename tests."""

    def supports_language(self, language: str) -> bool:
        return language in ["python"]

    async def parse_file(
        self, content: str, language: str, file_path: str
    ) -> tuple[list[ParsedSymbol], list[ParsedReference]]:
        return [], []

    async def extract_comments(
        self, content: str, language: str, file_path: str
    ) -> list[ParsedComment]:
        return []


def _make_commit(
    hash: str = "abc123",
    message: str = "Rename files",
    parent_hashes: list[str] | None = None,
) -> CommitInfo:
    date = datetime(2024, 1, 1, 12, 0, 0)
    return CommitInfo(
        hash=hash,
        short_hash=hash[:7],
        author_name="Test",
        author_email="test@test.com",
        author_date=date,
        committer_name="Test",
        committer_email="test@test.com",
        commit_date=date,
        message=message,
        parent_hashes=parent_hashes or [],
    )


@pytest.fixture
def file_rename_repo() -> InMemoryFileRenameRepository:
    return InMemoryFileRenameRepository()


@pytest.fixture
def use_case(
    git_service: FakeGitService,
    file_rename_repo: InMemoryFileRenameRepository,
) -> ProcessCommitUseCase:
    commit_repo = InMemoryCommitRepository()
    file_repo = InMemoryFileRepository()
    symbol_repo = InMemorySymbolRepository()
    reference_repo = InMemoryReferenceRepository(symbol_repo=symbol_repo)
    text_content_repo = InMemoryTextContentRepository()

    process_file = ProcessFileUseCase(
        git_service=git_service,
        file_repo=file_repo,
        symbol_repo=symbol_repo,
        reference_repo=reference_repo,
        text_content_repo=text_content_repo,
        parser_service=FakeParserService(),
        plaintext_parser=FakePlaintextParser(),
    )
    return ProcessCommitUseCase(
        commit_repo=commit_repo,
        file_repo=file_repo,
        git_service=git_service,
        text_content_repo=text_content_repo,
        process_file_use_case=process_file,
        file_rename_repo=file_rename_repo,
    )


class TestProcessCommitRenameDetection:
    """Tests for rename detection during commit processing."""

    @pytest.mark.asyncio
    async def test_detects_renames_in_commit(
        self,
        use_case: ProcessCommitUseCase,
        git_service: FakeGitService,
        file_rename_repo: InMemoryFileRenameRepository,
    ) -> None:
        """Renames detected by git should be stored in file_rename_repo."""
        git_service.files_in_commit["abc123"] = ["src/new_name.py"]
        git_service.renames_in_commit["abc123"] = [
            RenameInfo(
                old_path="src/old_name.py", new_path="src/new_name.py", similarity=95
            ),
        ]

        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )
        result = await use_case.execute(request)

        assert result.renames_found == 1
        renames = await file_rename_repo.get_renames_for_commit(1)
        assert len(renames) == 1
        assert renames[0].old_path == "src/old_name.py"
        assert renames[0].new_path == "src/new_name.py"
        assert renames[0].similarity == 95

    @pytest.mark.asyncio
    async def test_multiple_renames_in_single_commit(
        self,
        use_case: ProcessCommitUseCase,
        git_service: FakeGitService,
        file_rename_repo: InMemoryFileRenameRepository,
    ) -> None:
        git_service.files_in_commit["abc123"] = ["b.py", "d.py"]
        git_service.renames_in_commit["abc123"] = [
            RenameInfo(old_path="a.py", new_path="b.py", similarity=100),
            RenameInfo(old_path="c.py", new_path="d.py", similarity=80),
        ]

        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )
        result = await use_case.execute(request)

        assert result.renames_found == 2

    @pytest.mark.asyncio
    async def test_no_renames_in_commit(
        self,
        use_case: ProcessCommitUseCase,
        git_service: FakeGitService,
        file_rename_repo: InMemoryFileRenameRepository,
    ) -> None:
        """Commits with no renames should result in renames_found=0."""
        git_service.files_in_commit["abc123"] = ["src/main.py"]
        # No renames configured for this commit

        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )
        result = await use_case.execute(request)

        assert result.renames_found == 0

    @pytest.mark.asyncio
    async def test_no_rename_repo_skips_detection(
        self,
        git_service: FakeGitService,
    ) -> None:
        """When file_rename_repo is None, rename detection should be skipped."""
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository()
        symbol_repo = InMemorySymbolRepository()
        reference_repo = InMemoryReferenceRepository(symbol_repo=symbol_repo)
        text_content_repo = InMemoryTextContentRepository()

        process_file = ProcessFileUseCase(
            git_service=git_service,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=FakeParserService(),
            plaintext_parser=FakePlaintextParser(),
        )
        use_case_no_renames = ProcessCommitUseCase(
            commit_repo=commit_repo,
            file_repo=file_repo,
            git_service=git_service,
            text_content_repo=text_content_repo,
            process_file_use_case=process_file,
            # file_rename_repo is None (default)
        )

        git_service.files_in_commit["abc123"] = ["src/main.py"]
        git_service.renames_in_commit["abc123"] = [
            RenameInfo(old_path="old.py", new_path="new.py", similarity=90),
        ]

        request = ProcessCommitRequest(
            repository_id=1,
            commit_data=_make_commit(),
            repo_path=Path("/repos/test-repo"),
            branch="main",
        )
        result = await use_case_no_renames.execute(request)

        # Should not detect renames when repo is None
        assert result.renames_found == 0

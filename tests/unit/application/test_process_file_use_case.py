"""Tests for ProcessFileUseCase."""

from pathlib import Path

import pytest

from inxr2.application.use_cases.indexing.optimize_file_indexing import (
    OptimizeFileIndexingUseCase,
)
from inxr2.application.use_cases.indexing.process_file import (
    ProcessFileRequest,
    ProcessFileUseCase,
)
from tests.fixtures.test_doubles import (
    FakeGitService,
    FakePlaintextParser,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
    InMemoryTextContentRepository,
)


class FakeParserService:
    """Fake parser service for testing."""

    def __init__(self) -> None:
        self.comments_to_return: list[dict] = []

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
                "parent_symbol_id": None,
                "signature": None,
                "metadata": {},
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
        if self.comments_to_return:
            return self.comments_to_return
        return [
            {
                "content": f"Comment in {Path(file_path).name}",
                "content_type": "inline_comment",
                "source_line": 1,
            }
        ]


@pytest.fixture
def git_service() -> FakeGitService:
    return FakeGitService()


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
    git_service: FakeGitService,
    file_repo: InMemoryFileRepository,
    symbol_repo: InMemorySymbolRepository,
    reference_repo: InMemoryReferenceRepository,
    text_content_repo: InMemoryTextContentRepository,
    parser_service: FakeParserService,
) -> ProcessFileUseCase:
    optimize = OptimizeFileIndexingUseCase(
        file_repository=file_repo,
        symbol_repository=symbol_repo,
        reference_repository=reference_repo,
    )
    return ProcessFileUseCase(
        git_service=git_service,
        file_repo=file_repo,
        symbol_repo=symbol_repo,
        reference_repo=reference_repo,
        text_content_repo=text_content_repo,
        parser_service=parser_service,
        plaintext_parser=FakePlaintextParser(),
        optimize_use_case=optimize,
    )


class TestProcessFileUseCase:
    """Tests for ProcessFileUseCase."""

    @pytest.mark.asyncio
    async def test_successful_code_file_processing(
        self,
        use_case: ProcessFileUseCase,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
    ) -> None:
        """Test that a supported code file is parsed and symbols/references saved."""
        request = ProcessFileRequest(
            repository_id=1,
            commit_id=1,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
            content_hash_cache={},
        )

        result = await use_case.execute(request)

        assert result.processed is True
        assert result.skipped is False
        assert result.failed is False
        assert result.symbols_found > 0
        assert result.references_found > 0
        assert len(symbol_repo._symbols) > 0
        assert len(reference_repo._references) > 0

    @pytest.mark.asyncio
    async def test_content_hash_reuse_path(
        self,
        use_case: ProcessFileUseCase,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
    ) -> None:
        """Test that content-hash optimization reuses symbols from donor."""
        # First: process the file normally to populate cache
        cache: dict[str, int] = {}
        request1 = ProcessFileRequest(
            repository_id=1,
            commit_id=1,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
            content_hash_cache=cache,
        )
        result1 = await use_case.execute(request1)
        assert result1.processed is True
        assert result1.reused is False

        # Second: same content hash -> should reuse
        request2 = ProcessFileRequest(
            repository_id=1,
            commit_id=2,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
            content_hash_cache=cache,
        )
        result2 = await use_case.execute(request2)
        assert result2.processed is True
        assert result2.reused is True
        assert result2.symbols_reused > 0

    @pytest.mark.asyncio
    async def test_non_code_file_indexing(
        self,
        use_case: ProcessFileUseCase,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Test that non-code files (markdown, yaml) are indexed as text content."""
        request = ProcessFileRequest(
            repository_id=1,
            commit_id=1,
            file_path="README.md",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
            content_hash_cache={},
        )

        result = await use_case.execute(request)

        assert result.processed is True
        assert result.non_code_file_indexed is True
        # Check text content was saved
        all_text = text_content_repo.get_all()
        file_contents = [tc for tc in all_text if tc.source_type == "file_content"]
        assert len(file_contents) > 0

    @pytest.mark.asyncio
    async def test_unsupported_language_skips_file(
        self,
        use_case: ProcessFileUseCase,
    ) -> None:
        """Test that unsupported language files without plaintext support are skipped."""
        request = ProcessFileRequest(
            repository_id=1,
            commit_id=1,
            file_path="image.png",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
            content_hash_cache={},
        )

        result = await use_case.execute(request)

        # .png is not code, and plaintext parser doesn't support it
        assert result.skipped is True
        assert result.processed is False

    @pytest.mark.asyncio
    async def test_file_processing_error_returns_failed(
        self,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that exceptions during processing return a failed result."""

        class ErrorGitService(FakeGitService):
            def get_file_content(
                self, repo_path: Path, commit_hash: str, file_path: str
            ) -> str:
                raise RuntimeError("Git error")

        optimize = OptimizeFileIndexingUseCase(
            file_repository=file_repo,
            symbol_repository=symbol_repo,
            reference_repository=reference_repo,
        )
        use_case = ProcessFileUseCase(
            git_service=ErrorGitService(),
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
            optimize_use_case=optimize,
        )

        request = ProcessFileRequest(
            repository_id=1,
            commit_id=1,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
            content_hash_cache={},
        )

        result = await use_case.execute(request)

        assert result.failed is True
        assert result.error is not None
        assert "Git error" in result.error

    @pytest.mark.asyncio
    async def test_comment_docstring_extraction(
        self,
        use_case: ProcessFileUseCase,
        parser_service: FakeParserService,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Test that comments and docstrings are extracted and saved."""
        parser_service.comments_to_return = [
            {
                "content": "A docstring",
                "content_type": "docstring",
                "source_line": 1,
                "source_end_line": 3,
            },
            {
                "content": "An inline comment",
                "content_type": "inline_comment",
                "source_line": 5,
            },
        ]

        request = ProcessFileRequest(
            repository_id=1,
            commit_id=1,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
            content_hash_cache={},
        )

        result = await use_case.execute(request)

        assert result.docstrings_indexed == 1
        assert result.comments_indexed == 1

        all_text = text_content_repo.get_all()
        docstrings = [tc for tc in all_text if tc.content_type == "docstring"]
        comments = [tc for tc in all_text if tc.content_type == "inline_comment"]
        assert len(docstrings) == 1
        assert len(comments) == 1

    @pytest.mark.asyncio
    async def test_language_detection(
        self,
        use_case: ProcessFileUseCase,
    ) -> None:
        """Test that language is correctly detected from file extension."""
        # Python file
        result_py = await use_case.execute(
            ProcessFileRequest(
                repository_id=1,
                commit_id=1,
                file_path="main.py",
                commit_hash="abc123",
                repo_path=Path("/repos/test-repo"),
                content_hash_cache={},
            )
        )
        assert result_py.processed is True
        assert result_py.symbols_found > 0  # Python is supported

        # TypeScript file
        result_ts = await use_case.execute(
            ProcessFileRequest(
                repository_id=1,
                commit_id=1,
                file_path="app.ts",
                commit_hash="abc123",
                repo_path=Path("/repos/test-repo"),
                content_hash_cache={},
            )
        )
        assert result_ts.processed is True
        assert result_ts.symbols_found > 0

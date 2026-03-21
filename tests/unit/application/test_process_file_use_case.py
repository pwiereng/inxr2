"""Tests for ProcessFileUseCase."""

from pathlib import Path

import pytest

from inxr2.application.ports.services import ParserServicePort
from inxr2.application.use_cases.indexing.process_file import (
    MAX_TSVECTOR_CONTENT_BYTES,
    ProcessFileRequest,
    ProcessFileUseCase,
    truncate_for_tsvector,
)
from tests.fixtures.test_doubles import (
    FakeGitService,
    FakePlaintextParser,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
    InMemoryTextContentRepository,
)


class FakeParserService(ParserServicePort):
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
                "content_type": "single_line_comment",
                "source_line": 1,
            }
        ]


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
    return ProcessFileUseCase(
        git_service=git_service,
        file_repo=file_repo,
        symbol_repo=symbol_repo,
        reference_repo=reference_repo,
        text_content_repo=text_content_repo,
        parser_service=parser_service,
        plaintext_parser=FakePlaintextParser(),
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
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
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
        """Test that content-hash optimization reuses file version from cache."""
        # First: process the file normally to create a file version
        request1 = ProcessFileRequest(
            repository_id=1,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )
        result1 = await use_case.execute(request1)
        assert result1.processed is True
        assert result1.file_version_created is True

        # Second: same content hash -> should reuse existing file version
        request2 = ProcessFileRequest(
            repository_id=1,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )
        result2 = await use_case.execute(request2)
        assert result2.processed is True
        assert result2.file_version_created is False

    @pytest.mark.asyncio
    async def test_non_code_file_indexing(
        self,
        use_case: ProcessFileUseCase,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Test that non-code files (markdown, yaml) are indexed as text content."""
        request = ProcessFileRequest(
            repository_id=1,
            file_path="README.md",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )

        result = await use_case.execute(request)

        assert result.processed is True
        assert result.non_code_file_indexed is True
        # Check text content was saved
        all_text = text_content_repo.get_all()
        file_contents = [tc for tc in all_text if tc.source_type == "file_content"]
        assert len(file_contents) > 0

    @pytest.mark.asyncio
    async def test_binary_content_skips_file(
        self,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that binary content (null bytes) is skipped."""
        git_service = FakeGitService()
        git_service.set_file_content(
            repo_path="/repos/test-repo",
            commit_hash="abc123",
            file_path="image.png",
            content="PNG\x00\x00binary data",
        )
        use_case = ProcessFileUseCase(
            git_service=git_service,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = ProcessFileRequest(
            repository_id=1,
            file_path="image.png",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )

        result = await use_case.execute(request)

        assert result.skipped is True
        assert result.processed is False

    @pytest.mark.asyncio
    async def test_non_whitelisted_text_file_is_indexed(
        self,
        use_case: ProcessFileUseCase,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Regression test for GH #39: .sh files must be indexed as text content."""
        request = ProcessFileRequest(
            repository_id=1,
            file_path="scripts/deploy.sh",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )

        result = await use_case.execute(request)

        assert result.processed is True
        assert result.non_code_file_indexed is True
        file_contents = [
            tc for tc in text_content_repo.get_all() if tc.source_type == "file_content"
        ]
        assert len(file_contents) > 0

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

        use_case = ProcessFileUseCase(
            git_service=ErrorGitService(),
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = ProcessFileRequest(
            repository_id=1,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
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
                "content_type": "single_line_comment",
                "source_line": 5,
            },
        ]

        request = ProcessFileRequest(
            repository_id=1,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )

        result = await use_case.execute(request)

        assert result.docstrings_indexed == 1
        assert result.comments_indexed == 1

        all_text = text_content_repo.get_all()
        docstrings = [tc for tc in all_text if tc.content_type == "docstring"]
        comments = [tc for tc in all_text if tc.content_type == "single_line_comment"]
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
                file_path="main.py",
                commit_hash="abc123",
                repo_path=Path("/repos/test-repo"),
            )
        )
        assert result_py.processed is True
        assert result_py.symbols_found > 0  # Python is supported

        # TypeScript file
        result_ts = await use_case.execute(
            ProcessFileRequest(
                repository_id=1,
                file_path="app.ts",
                commit_hash="abc123",
                repo_path=Path("/repos/test-repo"),
            )
        )
        assert result_ts.processed is True
        assert result_ts.symbols_found > 0

    @pytest.mark.asyncio
    async def test_file_version_index_cache_hit(
        self,
        git_service: FakeGitService,
        use_case: ProcessFileUseCase,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
    ) -> None:
        """Test that file_version_index enables O(1) cache hit without DB query."""
        # Set identical content for both commits so content hashes match
        git_service.set_file_content(
            repo_path="/repos/test-repo",
            commit_hash="abc123",
            file_path="src/main.py",
            content="def hello():\n    print('hi')\n",
        )
        git_service.set_file_content(
            repo_path="/repos/test-repo",
            commit_hash="def456",
            file_path="src/main.py",
            content="def hello():\n    print('hi')\n",
        )

        # First: process normally to create a file version
        request1 = ProcessFileRequest(
            repository_id=1,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )
        result1 = await use_case.execute(request1)
        assert result1.file_version_created is True
        assert result1.file_id is not None

        # Build a file_version_index with the created file
        fvi = await file_repo.load_file_version_index(1)
        assert len(fvi) > 0

        # Second: same file with file_version_index → cache hit, no DB query
        request2 = ProcessFileRequest(
            repository_id=1,
            file_path="src/main.py",
            commit_hash="def456",
            repo_path=Path("/repos/test-repo"),
            file_version_index=fvi,
        )
        result2 = await use_case.execute(request2)
        assert result2.processed is True
        assert result2.file_version_created is False
        assert result2.file_id == result1.file_id
        # No new symbols should be created (cached path skips parsing)
        assert result2.symbols_found == 0

    @pytest.mark.asyncio
    async def test_file_version_index_updated_on_create(
        self,
        use_case: ProcessFileUseCase,
        git_service: FakeGitService,
    ) -> None:
        """Test that file_version_index is updated when a new file version is created."""
        fvi: dict[tuple[str, str], int] = {}

        request = ProcessFileRequest(
            repository_id=1,
            file_path="src/new_file.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
            file_version_index=fvi,
        )
        result = await use_case.execute(request)
        assert result.file_version_created is True
        assert result.file_id is not None

        # The fvi dict should now contain the new entry
        matching = [v for k, v in fvi.items() if k[0] == "src/new_file.py"]
        assert len(matching) == 1
        assert matching[0] == result.file_id

    @pytest.mark.asyncio
    async def test_file_version_index_blob_hash_fast_path(
        self,
        use_case: ProcessFileUseCase,
        git_service: FakeGitService,
    ) -> None:
        """Test fast path 1: blob hash → content hash → fvi lookup skips git read."""
        # First: process to populate blob_to_content_hash mapping
        blob_map: dict[str, str] = {}
        request1 = ProcessFileRequest(
            repository_id=1,
            file_path="src/main.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
            blob_hash="blob_aaa",
            blob_to_content_hash=blob_map,
        )
        result1 = await use_case.execute(request1)
        assert result1.file_version_created is True
        assert "blob_aaa" in blob_map

        # Build fvi from the created file
        fvi: dict[tuple[str, str], int] = {
            ("src/main.py", blob_map["blob_aaa"]): result1.file_id,  # type: ignore[dict-item]
        }

        # Second: same blob hash + fvi → fast path 1, no git content read
        request2 = ProcessFileRequest(
            repository_id=1,
            file_path="src/main.py",
            commit_hash="def456",
            repo_path=Path("/repos/test-repo"),
            blob_hash="blob_aaa",
            blob_to_content_hash=blob_map,
            file_version_index=fvi,
        )
        result2 = await use_case.execute(request2)
        assert result2.processed is True
        assert result2.file_version_created is False
        assert result2.file_id == result1.file_id


class TestParentSymbolIdResolution:
    """Tests for scope → parent_symbol_id resolution during indexing."""

    @pytest.mark.asyncio
    async def test_method_gets_parent_symbol_id_from_class(
        self,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Methods with scope='ClassName' get parent_symbol_id set to class ID."""

        class ClassMethodParserService(FakeParserService):
            async def parse_file(
                self, content: str, language: str, file_path: str
            ) -> tuple[list[dict], list[dict]]:
                symbols = [
                    {
                        "name": "MyClass",
                        "kind": "class",
                        "start_line": 1,
                        "start_column": 0,
                        "end_line": 20,
                        "end_column": 0,
                        "scope": None,
                    },
                    {
                        "name": "do_thing",
                        "kind": "method",
                        "start_line": 3,
                        "start_column": 4,
                        "end_line": 10,
                        "end_column": 0,
                        "scope": "MyClass",
                        "qualified_name": "MyClass.do_thing",
                    },
                    {
                        "name": "value",
                        "kind": "class_variable",
                        "start_line": 2,
                        "start_column": 4,
                        "end_line": 2,
                        "end_column": 14,
                        "scope": "MyClass",
                        "qualified_name": "MyClass.value",
                    },
                ]
                return symbols, []

        git_service = FakeGitService()
        use_case = ProcessFileUseCase(
            git_service=git_service,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=ClassMethodParserService(),
            plaintext_parser=FakePlaintextParser(),
        )

        request = ProcessFileRequest(
            repository_id=1,
            file_path="src/example.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )
        result = await use_case.execute(request)
        assert result.symbols_found == 3

        # Find the saved symbols
        all_symbols = list(symbol_repo._symbols.values())
        class_sym = next(s for s in all_symbols if s.name == "MyClass")
        method_sym = next(s for s in all_symbols if s.name == "do_thing")
        var_sym = next(s for s in all_symbols if s.name == "value")

        # Class has no parent
        assert class_sym.parent_symbol_id is None
        # Method and class_variable point to the class
        assert method_sym.parent_symbol_id == class_sym.id
        assert var_sym.parent_symbol_id == class_sym.id

    @pytest.mark.asyncio
    async def test_nested_function_gets_parent_from_qualified_name(
        self,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Nested functions with scope='Class.method' resolve via qualified_name."""

        class NestedParserService(FakeParserService):
            async def parse_file(
                self, content: str, language: str, file_path: str
            ) -> tuple[list[dict], list[dict]]:
                symbols = [
                    {
                        "name": "MyClass",
                        "kind": "class",
                        "start_line": 1,
                        "start_column": 0,
                        "end_line": 30,
                        "end_column": 0,
                        "scope": None,
                    },
                    {
                        "name": "do_thing",
                        "kind": "method",
                        "start_line": 3,
                        "start_column": 4,
                        "end_line": 20,
                        "end_column": 0,
                        "scope": "MyClass",
                        "qualified_name": "MyClass.do_thing",
                    },
                    {
                        "name": "helper",
                        "kind": "function",
                        "start_line": 10,
                        "start_column": 8,
                        "end_line": 15,
                        "end_column": 0,
                        "scope": "MyClass.do_thing",
                        "qualified_name": "MyClass.do_thing.helper",
                    },
                ]
                return symbols, []

        git_service = FakeGitService()
        use_case = ProcessFileUseCase(
            git_service=git_service,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=NestedParserService(),
            plaintext_parser=FakePlaintextParser(),
        )

        request = ProcessFileRequest(
            repository_id=1,
            file_path="src/nested.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )
        result = await use_case.execute(request)
        assert result.symbols_found == 3

        all_symbols = list(symbol_repo._symbols.values())
        class_sym = next(s for s in all_symbols if s.name == "MyClass")
        method_sym = next(s for s in all_symbols if s.name == "do_thing")
        helper_sym = next(s for s in all_symbols if s.name == "helper")

        assert class_sym.parent_symbol_id is None
        assert method_sym.parent_symbol_id == class_sym.id
        assert helper_sym.parent_symbol_id == method_sym.id

    @pytest.mark.asyncio
    async def test_top_level_function_has_no_parent(
        self,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Top-level symbols with no scope stay with parent_symbol_id=None."""

        class TopLevelParserService(FakeParserService):
            async def parse_file(
                self, content: str, language: str, file_path: str
            ) -> tuple[list[dict], list[dict]]:
                symbols = [
                    {
                        "name": "standalone_func",
                        "kind": "function",
                        "start_line": 1,
                        "start_column": 0,
                        "end_line": 5,
                        "end_column": 0,
                        "scope": None,
                    },
                ]
                return symbols, []

        git_service = FakeGitService()
        use_case = ProcessFileUseCase(
            git_service=git_service,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=TopLevelParserService(),
            plaintext_parser=FakePlaintextParser(),
        )

        request = ProcessFileRequest(
            repository_id=1,
            file_path="src/top.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )
        result = await use_case.execute(request)
        assert result.symbols_found == 1

        func_sym = list(symbol_repo._symbols.values())[0]
        assert func_sym.parent_symbol_id is None


class TestTruncateForTsvector:
    """Tests for the truncate_for_tsvector utility function."""

    def test_short_content_unchanged(self) -> None:
        """Content under the limit is returned unchanged."""
        content = "Hello world"
        result, was_truncated = truncate_for_tsvector(content)
        assert result == content
        assert was_truncated is False

    def test_empty_content_unchanged(self) -> None:
        """Empty content is returned unchanged."""
        result, was_truncated = truncate_for_tsvector("")
        assert result == ""
        assert was_truncated is False

    def test_content_at_limit_unchanged(self) -> None:
        """Content exactly at the byte limit is not truncated."""
        content = "a" * MAX_TSVECTOR_CONTENT_BYTES
        assert len(content.encode("utf-8")) == MAX_TSVECTOR_CONTENT_BYTES
        result, was_truncated = truncate_for_tsvector(content)
        assert result == content
        assert was_truncated is False

    def test_content_over_limit_is_truncated(self) -> None:
        """Content exceeding the byte limit is truncated."""
        content = "a" * (MAX_TSVECTOR_CONTENT_BYTES + 10_000)
        result, was_truncated = truncate_for_tsvector(content)
        assert len(result.encode("utf-8")) <= MAX_TSVECTOR_CONTENT_BYTES
        assert was_truncated is True

    def test_multibyte_content_truncated_safely(self) -> None:
        """Multi-byte characters are not split mid-character."""
        # Each emoji is 4 bytes in UTF-8
        emoji = "\U0001f600"  # 😀
        assert len(emoji.encode("utf-8")) == 4
        # Fill up to just over the limit
        count = (MAX_TSVECTOR_CONTENT_BYTES // 4) + 100
        content = emoji * count
        result, was_truncated = truncate_for_tsvector(content)
        assert was_truncated is True
        # Must be under the byte limit
        encoded = result.encode("utf-8")
        assert len(encoded) <= MAX_TSVECTOR_CONTENT_BYTES
        # Result should be the longest valid UTF-8 prefix within the limit.
        # Since each emoji is 4 bytes, truncation should land on a 4-byte
        # boundary (MAX_TSVECTOR_CONTENT_BYTES // 4 emojis).
        expected_count = MAX_TSVECTOR_CONTENT_BYTES // 4
        assert result == emoji * expected_count


class TestLargeContentTruncation:
    """Tests that large content is truncated during file processing."""

    @pytest.mark.asyncio
    async def test_large_non_code_file_content_is_truncated(
        self,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Non-code file exceeding tsvector limit should be truncated, not fail."""
        large_content = "x" * (MAX_TSVECTOR_CONTENT_BYTES + 100_000)
        git_service = FakeGitService()
        git_service.set_file_content(
            repo_path="/repos/test-repo",
            commit_hash="abc123",
            file_path="large_file.md",
            content=large_content,
        )

        use_case = ProcessFileUseCase(
            git_service=git_service,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = ProcessFileRequest(
            repository_id=1,
            file_path="large_file.md",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )

        result = await use_case.execute(request)

        # Should succeed, not fail
        assert result.failed is False
        assert result.non_code_file_indexed is True

        # All saved text contents should be under the limit
        for tc in text_content_repo.get_all():
            assert len(tc.content.encode("utf-8")) <= MAX_TSVECTOR_CONTENT_BYTES

    @pytest.mark.asyncio
    async def test_large_comment_content_is_truncated(
        self,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Code file with comment exceeding tsvector limit should truncate, not fail."""
        large_comment = "x" * (MAX_TSVECTOR_CONTENT_BYTES + 50_000)

        class LargeCommentParserService(FakeParserService):
            async def extract_comments(
                self, content: str, language: str, file_path: str
            ) -> list[dict]:
                return [
                    {
                        "content": large_comment,
                        "content_type": "block_comment",
                        "source_line": 1,
                        "source_end_line": 10,
                    }
                ]

        git_service = FakeGitService()
        use_case = ProcessFileUseCase(
            git_service=git_service,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            text_content_repo=text_content_repo,
            parser_service=LargeCommentParserService(),
            plaintext_parser=FakePlaintextParser(),
        )

        request = ProcessFileRequest(
            repository_id=1,
            file_path="src/big.py",
            commit_hash="abc123",
            repo_path=Path("/repos/test-repo"),
        )

        result = await use_case.execute(request)

        assert result.failed is False
        assert result.comments_indexed == 1

        # The saved comment should be truncated to fit
        for tc in text_content_repo.get_all():
            if tc.content_type == "block_comment":
                assert len(tc.content.encode("utf-8")) <= MAX_TSVECTOR_CONTENT_BYTES

"""
Process file use case.

Extracts symbols, references, comments, and text content from a single file
during indexing. This was extracted from DefaultIndexingOrchestrator to keep
the orchestrator focused on coordination.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from inxr2.domain.entities import (
    File,
    Reference,
    Symbol,
    TextContent,
)
from inxr2.domain.value_objects import (
    ReferenceType,
    SymbolKind,
    TextSearchSourceType,
)

from ...ports.repositories import (
    FileRepositoryPort,
    ReferenceRepositoryPort,
    SymbolRepositoryPort,
    TextContentRepositoryPort,
)
from ...ports.services import GitServicePort, PlaintextParserPort
from .optimize_file_indexing import (
    OptimizeFileIndexingRequest,
    OptimizeFileIndexingUseCase,
)


@dataclass
class ProcessFileRequest:
    """Request to process a single file during indexing."""

    repository_id: int
    commit_id: int
    file_path: str
    commit_hash: str
    repo_path: Path
    content_hash_cache: dict[str, int]  # mutated in-place (adds new entries)


@dataclass
class ProcessFileResult:
    """Result of processing a single file."""

    processed: bool
    skipped: bool
    failed: bool
    reused: bool
    symbols_found: int
    references_found: int
    symbols_reused: int
    references_reused: int
    lines_indexed: int
    comments_indexed: int
    docstrings_indexed: int
    non_code_file_indexed: bool
    error: str | None = None
    db_inserts: int = 0
    db_selects: int = 0


class ProcessFileUseCase:
    """
    Use case for processing a single file during indexing.

    Handles:
    - Reading file content from git
    - Content-hash optimization (reuse from donor file)
    - Parsing code files for symbols and references
    - Extracting comments and docstrings
    - Indexing non-code files as text content
    """

    def __init__(
        self,
        git_service: GitServicePort,
        file_repo: FileRepositoryPort,
        symbol_repo: SymbolRepositoryPort,
        reference_repo: ReferenceRepositoryPort,
        text_content_repo: TextContentRepositoryPort,
        parser_service: Any,  # ParserServicePort
        plaintext_parser: PlaintextParserPort,
        optimize_use_case: OptimizeFileIndexingUseCase,
    ) -> None:
        self._git_service = git_service
        self._file_repo = file_repo
        self._symbol_repo = symbol_repo
        self._reference_repo = reference_repo
        self._text_content_repo = text_content_repo
        self._parser_service = parser_service
        self._plaintext_parser = plaintext_parser
        self._optimize_use_case = optimize_use_case

    async def execute(self, request: ProcessFileRequest) -> ProcessFileResult:
        """Process a single file: parse, extract symbols/references, save."""
        try:
            return await self._do_process(request)
        except Exception as e:
            return ProcessFileResult(
                processed=False,
                skipped=False,
                failed=True,
                reused=False,
                symbols_found=0,
                references_found=0,
                symbols_reused=0,
                references_reused=0,
                lines_indexed=0,
                comments_indexed=0,
                docstrings_indexed=0,
                non_code_file_indexed=False,
                error=f"Failed to process {request.file_path}: {e}",
            )

    async def _do_process(self, request: ProcessFileRequest) -> ProcessFileResult:
        """Inner processing logic (called within try/except)."""
        db_inserts = 0
        db_selects = 0

        # Get file content
        content = self._git_service.get_file_content(
            repo_path=request.repo_path,
            commit_hash=request.commit_hash,
            file_path=request.file_path,
        )

        # Calculate content hash
        content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()

        # Detect language
        language = self._detect_language(request.file_path)

        # Create file record
        file_entity = File(
            id=None,
            repository_id=request.repository_id,
            commit_id=request.commit_id,
            path=request.file_path,
            content_hash=content_hash,
            size_bytes=len(content.encode("utf-8")),
            language=language,
            line_count=content.count("\n") + 1,
        )
        db_file = await self._file_repo.save(file_entity)
        db_inserts += 1
        file_id = db_file.id
        assert file_id is not None, "File must have an ID after save"

        # Try content-hash optimization
        optimize_request = OptimizeFileIndexingRequest(
            target_file_id=file_id,
            target_commit_id=request.commit_id,
            target_repository_id=request.repository_id,
            content_hash=content_hash,
            content_hash_cache=request.content_hash_cache,
        )
        optimization_result = await self._optimize_use_case.execute(optimize_request)

        if optimization_result.optimization_applied:
            # Reused symbols/references from donor file
            request.content_hash_cache[content_hash] = file_id
            db_selects += 2
            db_inserts += (
                optimization_result.symbols_copied
                + optimization_result.references_copied
            )
            return ProcessFileResult(
                processed=True,
                skipped=False,
                failed=False,
                reused=True,
                symbols_found=optimization_result.symbols_copied,
                references_found=optimization_result.references_copied,
                symbols_reused=optimization_result.symbols_copied,
                references_reused=optimization_result.references_copied,
                lines_indexed=file_entity.line_count or 0,
                comments_indexed=0,
                docstrings_indexed=0,
                non_code_file_indexed=False,
                db_inserts=db_inserts,
                db_selects=db_selects,
            )

        # Parse file and extract symbols/references
        if language and self._parser_service.supports_language(language):
            symbols_data, references_data = await self._parser_service.parse_file(
                content=content,
                language=language,
                file_path=request.file_path,
            )

            # Extract and save comments
            comments_indexed, docstrings_indexed, comment_errors = (
                await self._extract_and_save_comments(
                    content=content,
                    language=language,
                    file_path_str=request.file_path,
                    repository_id=request.repository_id,
                    commit_id=request.commit_id,
                    file_id=file_id,
                )
            )
            comment_inserts = comments_indexed + docstrings_indexed

            # Save symbols
            symbols_found = 0
            for symbol_data in symbols_data:
                symbol = Symbol(
                    id=None,
                    file_id=file_id,
                    repository_id=request.repository_id,
                    commit_id=request.commit_id,
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
                db_inserts += 1
                symbols_found += 1

            # Save references
            references_found = 0
            for ref_data in references_data:
                reference_text = ref_data.get("text") or ref_data.get(
                    "reference_text", ""
                )
                reference_type = ref_data.get("type") or ref_data.get(
                    "reference_type", "usage"
                )
                source_column = ref_data["source_column"]
                source_end_column = ref_data.get(
                    "source_end_column",
                    source_column + len(reference_text),
                )

                reference = Reference(
                    id=None,
                    repository_id=request.repository_id,
                    commit_id=request.commit_id,
                    source_file_id=file_id,
                    source_line=ref_data["source_line"],
                    source_column=source_column,
                    source_end_column=source_end_column,
                    reference_text=reference_text,
                    reference_type=ReferenceType(reference_type),
                    target_symbol_id=None,
                )
                await self._reference_repo.save(reference)
                db_inserts += 1
                references_found += 1

            # Add to cache
            request.content_hash_cache[content_hash] = file_id

            return ProcessFileResult(
                processed=True,
                skipped=False,
                failed=False,
                reused=False,
                symbols_found=symbols_found,
                references_found=references_found,
                symbols_reused=0,
                references_reused=0,
                lines_indexed=file_entity.line_count or 0,
                comments_indexed=comments_indexed,
                docstrings_indexed=docstrings_indexed,
                non_code_file_indexed=False,
                error=comment_errors,
                db_inserts=db_inserts + comment_inserts,
                db_selects=db_selects,
            )

        # Not a supported code file - try parsing as plaintext/non-code file
        indexed_as_plaintext = await self._index_non_code_file(
            content=content,
            file_path_str=request.file_path,
            repository_id=request.repository_id,
            commit_id=request.commit_id,
            file_id=file_id,
        )

        if indexed_as_plaintext.indexed:
            return ProcessFileResult(
                processed=True,
                skipped=False,
                failed=False,
                reused=False,
                symbols_found=0,
                references_found=0,
                symbols_reused=0,
                references_reused=0,
                lines_indexed=file_entity.line_count or 0,
                comments_indexed=0,
                docstrings_indexed=0,
                non_code_file_indexed=True,
                error=indexed_as_plaintext.error,
                db_inserts=db_inserts + indexed_as_plaintext.inserts,
                db_selects=db_selects,
            )

        return ProcessFileResult(
            processed=False,
            skipped=True,
            failed=False,
            reused=False,
            symbols_found=0,
            references_found=0,
            symbols_reused=0,
            references_reused=0,
            lines_indexed=0,
            comments_indexed=0,
            docstrings_indexed=0,
            non_code_file_indexed=False,
            db_inserts=db_inserts,
            db_selects=db_selects,
        )

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

    async def _extract_and_save_comments(
        self,
        content: str,
        language: str,
        file_path_str: str,
        repository_id: int,
        commit_id: int,
        file_id: int,
    ) -> tuple[int, int, str | None]:
        """Extract comments and docstrings from a file and save to database.

        Returns:
            Tuple of (comments_indexed, docstrings_indexed, error_message_or_none)
        """
        comments_indexed = 0
        docstrings_indexed = 0
        try:
            comments_data = await self._parser_service.extract_comments(
                content=content,
                language=language,
                file_path=file_path_str,
            )

            for comment_data in comments_data:
                comment_content = comment_data.get("content", "")
                if not comment_content or not comment_content.strip():
                    continue

                content_type = comment_data.get("content_type", "single_line_comment")
                if content_type == "docstring":
                    source_type = TextSearchSourceType.DOCSTRING.value
                    docstrings_indexed += 1
                else:
                    source_type = TextSearchSourceType.COMMENT.value
                    comments_indexed += 1

                text_content = TextContent(
                    id=None,
                    repository_id=repository_id,
                    commit_id=commit_id,
                    source_type=source_type,
                    source_file_id=file_id,
                    source_line=comment_data["source_line"],
                    source_end_line=comment_data.get("source_end_line"),
                    content=comment_content,
                    language=language,
                    content_type=content_type,
                )
                await self._text_content_repo.save(text_content)

        except Exception as e:
            return (
                comments_indexed,
                docstrings_indexed,
                f"Failed to extract comments from {file_path_str}: {e}",
            )

        return comments_indexed, docstrings_indexed, None

    @dataclass
    class _NonCodeResult:
        indexed: bool
        inserts: int
        error: str | None = None

    async def _index_non_code_file(
        self,
        content: str,
        file_path_str: str,
        repository_id: int,
        commit_id: int,
        file_id: int,
    ) -> _NonCodeResult:
        """Index non-code files (markdown, YAML, etc.) as searchable text content."""
        try:
            if not self._plaintext_parser.supports_file(file_path_str):
                return self._NonCodeResult(indexed=False, inserts=0)

            chunks = self._plaintext_parser.parse(content, file_path_str)
            if not chunks:
                return self._NonCodeResult(indexed=False, inserts=0)

            inserts = 0
            for chunk in chunks:
                text_content = TextContent(
                    id=None,
                    repository_id=repository_id,
                    commit_id=commit_id,
                    source_type=TextSearchSourceType.FILE_CONTENT.value,
                    source_file_id=file_id,
                    source_line=chunk["source_line"],
                    source_end_line=chunk.get("source_end_line"),
                    content=chunk["content"],
                    language=None,
                    content_type=chunk["content_type"],
                )
                await self._text_content_repo.save(text_content)
                inserts += 1

            return self._NonCodeResult(indexed=True, inserts=inserts)

        except Exception as e:
            return self._NonCodeResult(
                indexed=False,
                inserts=0,
                error=f"Failed to index non-code file {file_path_str}: {e}",
            )

"""
Process file use case.

Extracts symbols, references, comments, and text content from a single file
during indexing. Uses content-addressable file versioning: if a file version
(repo, path, content_hash) already exists, skips parsing entirely.
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from inxr2.domain.entities import (
    Reference,
    Symbol,
    TextContent,
)
from inxr2.domain.services.language_detector import LanguageDetector
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
from ...ports.services import GitServicePort, ParserServicePort, PlaintextParserPort

logger = logging.getLogger(__name__)

# PostgreSQL tsvector has a hard limit of 1,048,575 bytes.
# We use a slightly lower limit to leave room for overhead.
MAX_TSVECTOR_CONTENT_BYTES = 1_000_000


def truncate_for_tsvector(content: str) -> str:
    """Truncate content to fit within PostgreSQL's tsvector byte limit.

    Truncates on a UTF-8 byte boundary so multi-byte characters are never split.
    """
    encoded = content.encode("utf-8")
    if len(encoded) <= MAX_TSVECTOR_CONTENT_BYTES:
        return content
    # Truncate the raw bytes, then decode ignoring any trailing partial character
    truncated = encoded[:MAX_TSVECTOR_CONTENT_BYTES]
    return truncated.decode("utf-8", errors="ignore")


@dataclass
class ProcessFileRequest:
    """Request to process a single file during indexing."""

    repository_id: int
    file_path: str
    commit_hash: str
    repo_path: Path
    blob_hash: str | None = None  # git blob hash for fast skip
    blob_to_content_hash: dict[str, str] | None = None  # blob hash -> content hash
    # Pre-loaded index: (path, content_hash) -> file_id.
    # When provided, skips individual DB queries for cached file versions.
    file_version_index: dict[tuple[str, str], int] | None = None


@dataclass
class ProcessFileResult:
    """Result of processing a single file."""

    processed: bool
    skipped: bool
    failed: bool
    file_id: int | None  # file version ID for commit_files linking
    file_version_created: bool  # True if a new file version was created
    symbols_found: int
    references_found: int
    lines_indexed: int
    comments_indexed: int
    docstrings_indexed: int
    non_code_file_indexed: bool
    error: str | None = None


class ProcessFileUseCase:
    """
    Use case for processing a single file during indexing.

    Uses content-addressable file versioning:
    - A file version is uniquely identified by (repo_id, path, content_hash)
    - If a version already exists, we skip parsing entirely (no copying needed)
    - If it's new, we parse and save symbols/references
    - The caller (ProcessCommitUseCase) handles linking file_id to commit
    """

    def __init__(
        self,
        git_service: GitServicePort,
        file_repo: FileRepositoryPort,
        symbol_repo: SymbolRepositoryPort,
        reference_repo: ReferenceRepositoryPort,
        text_content_repo: TextContentRepositoryPort,
        parser_service: ParserServicePort,
        plaintext_parser: PlaintextParserPort,
    ) -> None:
        self._git_service = git_service
        self._file_repo = file_repo
        self._symbol_repo = symbol_repo
        self._reference_repo = reference_repo
        self._text_content_repo = text_content_repo
        self._parser_service = parser_service
        self._plaintext_parser = plaintext_parser

    async def execute(self, request: ProcessFileRequest) -> ProcessFileResult:
        """Process a single file: find or create version, parse if new."""
        try:
            return await self._do_process(request)
        except Exception as e:  # Catch-all: resilience boundary for per-file processing
            return ProcessFileResult(
                processed=False,
                skipped=False,
                failed=True,
                file_id=None,
                file_version_created=False,
                symbols_found=0,
                references_found=0,
                lines_indexed=0,
                comments_indexed=0,
                docstrings_indexed=0,
                non_code_file_indexed=False,
                error=f"Failed to process {request.file_path}: {e}",
            )

    async def _do_process(self, request: ProcessFileRequest) -> ProcessFileResult:
        """Inner processing logic."""
        fvi = request.file_version_index  # pre-loaded (path, content_hash)->file_id

        # Fast path 1: blob hash → content hash → file_version_index lookup
        # Avoids BOTH git content read AND DB query.
        known_content_hash = self._lookup_blob_hash(request)
        if known_content_hash:
            # Check in-memory index first (O(1) dict lookup)
            if fvi is not None:
                cached_id = fvi.get((request.file_path, known_content_hash))
                if cached_id is not None:
                    return ProcessFileResult(
                        processed=True,
                        skipped=False,
                        failed=False,
                        file_id=cached_id,
                        file_version_created=False,
                        symbols_found=0,
                        references_found=0,
                        lines_indexed=0,
                        comments_indexed=0,
                        docstrings_indexed=0,
                        non_code_file_indexed=False,
                    )
            # Fallback to DB query
            existing_files = await self._file_repo.find_by_content_hash(
                known_content_hash,
                repository_id=request.repository_id,
                path=request.file_path,
            )
            existing_version = existing_files[0] if existing_files else None
            if existing_version is not None:
                return ProcessFileResult(
                    processed=True,
                    skipped=False,
                    failed=False,
                    file_id=existing_version.id,
                    file_version_created=False,
                    symbols_found=0,
                    references_found=0,
                    lines_indexed=0,
                    comments_indexed=0,
                    docstrings_indexed=0,
                    non_code_file_indexed=False,
                )
            # Not found — fall through to full processing (read content, create properly)

        # Read file content from git
        content = self._git_service.get_file_content(
            repo_path=request.repo_path,
            commit_hash=request.commit_hash,
            file_path=request.file_path,
        )

        # Calculate content hash
        content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()

        # Record blob → content hash mapping for future fast skip
        if request.blob_hash and request.blob_to_content_hash is not None:
            request.blob_to_content_hash[request.blob_hash] = content_hash

        # Fast path 2: check file_version_index after computing content hash.
        # Avoids the DB query in find_or_create_version for cached files.
        if fvi is not None:
            cached_id = fvi.get((request.file_path, content_hash))
            if cached_id is not None:
                return ProcessFileResult(
                    processed=True,
                    skipped=False,
                    failed=False,
                    file_id=cached_id,
                    file_version_created=False,
                    symbols_found=0,
                    references_found=0,
                    lines_indexed=0,
                    comments_indexed=0,
                    docstrings_indexed=0,
                    non_code_file_indexed=False,
                )

        # Detect language using full LanguageDetector (60+ extensions, fixes #35)
        language = LanguageDetector.detect(request.file_path)

        # Extract file extension (e.g., ".py", ".tsx")
        extension = Path(request.file_path).suffix.lower() or None

        # Find or create file version
        content_bytes = content.encode("utf-8")
        line_count = content.count("\n") + 1
        file_entity, created = await self._file_repo.find_or_create_version(
            repository_id=request.repository_id,
            path=request.file_path,
            content_hash=content_hash,
            size_bytes=len(content_bytes),
            language=language,
            extension=extension,
            line_count=line_count,
        )
        file_id = file_entity.id
        assert file_id is not None

        # Register newly created file in the index for subsequent lookups
        if created and fvi is not None:
            fvi[(request.file_path, content_hash)] = file_id

        if not created:
            # File version already exists — symbols/references already saved
            return ProcessFileResult(
                processed=True,
                skipped=False,
                failed=False,
                file_id=file_id,
                file_version_created=False,
                symbols_found=0,
                references_found=0,
                lines_indexed=0,
                comments_indexed=0,
                docstrings_indexed=0,
                non_code_file_indexed=False,
            )

        # New file version — parse and save symbols/references
        if language and self._parser_service.supports_language(language):
            symbols_data, references_data = await self._parser_service.parse_file(
                content=content,
                language=language,
                file_path=request.file_path,
            )

            # Extract and save comments (file-derived, commit_id=None)
            comments_indexed, docstrings_indexed, comment_errors = (
                await self._extract_and_save_comments(
                    content=content,
                    language=language,
                    file_path_str=request.file_path,
                    repository_id=request.repository_id,
                    file_id=file_id,
                )
            )

            # Filter out symbols with empty names (can happen with
            # macro-heavy code where tree-sitter produces empty identifiers)
            valid_symbols_data = []
            for sd in symbols_data:
                if sd.get("name"):
                    valid_symbols_data.append(sd)
                else:
                    logger.debug(
                        "Skipping symbol with empty name at line %d in %s",
                        sd.get("start_line", 0),
                        request.file_path,
                    )

            # Save symbols (batch)
            symbols = [
                Symbol(
                    id=None,
                    file_id=file_id,
                    repository_id=request.repository_id,
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
                for symbol_data in valid_symbols_data
            ]
            if symbols:
                await self._symbol_repo.save_many(symbols)
            symbols_found = len(symbols)

            # Save references (batch)
            references = []
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

                references.append(
                    Reference(
                        id=None,
                        repository_id=request.repository_id,
                        source_file_id=file_id,
                        source_line=ref_data["source_line"],
                        source_column=source_column,
                        source_end_column=source_end_column,
                        reference_text=reference_text,
                        reference_type=ReferenceType(reference_type),
                        target_symbol_id=None,
                    )
                )
            if references:
                await self._reference_repo.save_many(references)
            references_found = len(references)

            return ProcessFileResult(
                processed=True,
                skipped=False,
                failed=False,
                file_id=file_id,
                file_version_created=True,
                symbols_found=symbols_found,
                references_found=references_found,
                lines_indexed=line_count,
                comments_indexed=comments_indexed,
                docstrings_indexed=docstrings_indexed,
                non_code_file_indexed=False,
                error=comment_errors,
            )

        # Not a supported code file — try parsing as plaintext/non-code file
        indexed_as_plaintext = await self._index_non_code_file(
            content=content,
            file_path_str=request.file_path,
            repository_id=request.repository_id,
            file_id=file_id,
        )

        if indexed_as_plaintext.indexed:
            return ProcessFileResult(
                processed=True,
                skipped=False,
                failed=False,
                file_id=file_id,
                file_version_created=True,
                symbols_found=0,
                references_found=0,
                lines_indexed=line_count,
                comments_indexed=0,
                docstrings_indexed=0,
                non_code_file_indexed=True,
                error=indexed_as_plaintext.error,
            )

        return ProcessFileResult(
            processed=False,
            skipped=True,
            failed=False,
            file_id=file_id,
            file_version_created=True,
            symbols_found=0,
            references_found=0,
            lines_indexed=0,
            comments_indexed=0,
            docstrings_indexed=0,
            non_code_file_indexed=False,
        )

    @staticmethod
    def _lookup_blob_hash(request: ProcessFileRequest) -> str | None:
        """Look up content hash from blob hash if available."""
        if (
            request.blob_hash
            and request.blob_to_content_hash is not None
            and request.blob_hash in request.blob_to_content_hash
        ):
            return request.blob_to_content_hash[request.blob_hash]
        return None

    async def _extract_and_save_comments(
        self,
        content: str,
        language: str,
        file_path_str: str,
        repository_id: int,
        file_id: int,
    ) -> tuple[int, int, str | None]:
        """Extract comments and docstrings from a file and save to database.

        File-derived text content uses commit_id=None since it belongs
        to the file version, not a specific commit.

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

            text_contents: list[TextContent] = []
            for comment_data in comments_data:
                comment_content = comment_data.get("content", "")
                if not comment_content or not comment_content.strip():
                    continue

                comment_content = truncate_for_tsvector(comment_content)
                if len(comment_content.encode("utf-8")) < len(
                    comment_data.get("content", "").encode("utf-8")
                ):
                    logger.warning(
                        "Truncated comment content in %s (line %d) "
                        "to fit tsvector limit (%d bytes)",
                        file_path_str,
                        comment_data.get("source_line", 0),
                        MAX_TSVECTOR_CONTENT_BYTES,
                    )

                content_type = comment_data.get("content_type", "single_line_comment")
                if content_type == "docstring":
                    source_type = TextSearchSourceType.DOCSTRING.value
                    docstrings_indexed += 1
                else:
                    source_type = TextSearchSourceType.COMMENT.value
                    comments_indexed += 1

                text_contents.append(
                    TextContent(
                        id=None,
                        repository_id=repository_id,
                        commit_id=None,  # file-derived, not commit-specific
                        source_type=source_type,
                        source_file_id=file_id,
                        source_line=comment_data["source_line"],
                        source_end_line=comment_data.get("source_end_line"),
                        content=comment_content,
                        language=language,
                        content_type=content_type,
                    )
                )
            if text_contents:
                await self._text_content_repo.save_batch(text_contents)

        except (UnicodeDecodeError, OSError, RuntimeError) as e:
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
        file_id: int,
    ) -> _NonCodeResult:
        """Index non-code files (markdown, YAML, etc.) as searchable text content."""
        try:
            # Skip binary content (null bytes indicate binary data).
            # In production, binary files already fail at get_file_content()
            # with UnicodeDecodeError, but this guards edge cases.
            if "\x00" in content:
                return self._NonCodeResult(indexed=False, inserts=0)

            chunks = self._plaintext_parser.parse(content, file_path_str)
            if not chunks:
                return self._NonCodeResult(indexed=False, inserts=0)

            text_contents: list[TextContent] = []
            for chunk in chunks:
                chunk_content = truncate_for_tsvector(chunk["content"])
                if len(chunk_content.encode("utf-8")) < len(
                    chunk["content"].encode("utf-8")
                ):
                    logger.warning(
                        "Truncated text content in %s (line %d) "
                        "to fit tsvector limit (%d bytes)",
                        file_path_str,
                        chunk.get("source_line", 0),
                        MAX_TSVECTOR_CONTENT_BYTES,
                    )
                text_contents.append(
                    TextContent(
                        id=None,
                        repository_id=repository_id,
                        commit_id=None,  # file-derived, not commit-specific
                        source_type=TextSearchSourceType.FILE_CONTENT.value,
                        source_file_id=file_id,
                        source_line=chunk["source_line"],
                        source_end_line=chunk.get("source_end_line"),
                        content=chunk_content,
                        language=None,
                        content_type=chunk["content_type"],
                    )
                )
            if text_contents:
                await self._text_content_repo.save_batch(text_contents)

            return self._NonCodeResult(indexed=True, inserts=len(text_contents))

        except (UnicodeDecodeError, OSError, RuntimeError) as e:
            return self._NonCodeResult(
                indexed=False,
                inserts=0,
                error=f"Failed to index non-code file {file_path_str}: {e}",
            )

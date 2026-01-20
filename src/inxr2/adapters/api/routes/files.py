"""File API endpoints for code browsing."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from ....infrastructure.dependencies import (
    CommitAdapter,
    FileAdapter,
    GitServiceDep,
    ReferenceAdapter,
    RepositoryAdapter,
    SymbolAdapter,
)
from ..validation import validate_path, validate_repo_name

router = APIRouter(prefix="/files", tags=["files"])


# Response models
class FileContentResponse(BaseModel):
    """File content response model."""

    id: int
    path: str
    language: str | None
    content: str
    line_count: int
    size_bytes: int


class FileSymbolResponse(BaseModel):
    """Symbol in a file response model."""

    id: int
    name: str
    qualified_name: str | None
    kind: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    signature: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FileSymbolsResponse(BaseModel):
    """List of symbols in a file."""

    file_id: int
    file_path: str
    symbols: list[FileSymbolResponse]
    total: int


class FileReferenceResponse(BaseModel):
    """Reference from a file response model."""

    id: int
    reference_text: str
    reference_type: str
    source_line: int
    source_column: int
    target_symbol_id: int | None

    model_config = ConfigDict(from_attributes=True)


class FileReferencesResponse(BaseModel):
    """List of references from a file."""

    file_id: int
    file_path: str
    references: list[FileReferenceResponse]
    total: int


class FileVersionResponse(BaseModel):
    """A single version of a file."""

    commit_id: int
    commit_hash: str
    short_hash: str
    commit_date: str
    message: str
    content_hash: str


class FileHistoryResponse(BaseModel):
    """File version history response."""

    path: str
    repository_name: str
    versions: list[FileVersionResponse]
    total: int


@router.get("/by-path", response_model=FileContentResponse)
async def get_file_content_by_path(
    repo: str,
    path: str,
    repo_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
    commit_adapter: CommitAdapter,
    git_service: GitServiceDep,
    commit: str | None = None,
) -> FileContentResponse:
    """
    Get file content by repository name and file path.

    Query parameters:
    - repo: Repository name
    - path: File path within the repository
    - commit: Commit hash (optional, defaults to latest version for time travel)
    """
    # Validate inputs to prevent path traversal and injection
    repo = validate_repo_name(repo)
    path = validate_path(path)

    # Get repository by name
    repository = await repo_adapter.find_by_name(repo)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    repository_id = repository.id if repository.id is not None else 0

    # Get file by repository and path (and optionally commit)
    if commit:
        # Time travel mode: get file at specific commit
        file = await file_adapter.find_by_repository_path_and_commit_hash(
            repository_id, path, commit
        )
        if not file:
            raise HTTPException(
                status_code=404,
                detail=f"File not found at commit {commit}",
            )
    else:
        # Default: get latest version
        file = await file_adapter.find_by_repository_and_path(repository_id, path)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

    # Get commit info to get the hash
    commit_record = await commit_adapter.find_by_id(file.commit_id)
    if not commit_record:
        raise HTTPException(status_code=404, detail="Commit not found")

    # The repository URL is the local path for indexed repos
    repo_path = Path(repository.url)
    if not repo_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Repository path not found: {repository.url}",
        )

    # Fetch content from git
    try:
        content = git_service.get_file_content(
            repo_path=repo_path,
            commit_hash=commit_record.commit_hash.value,
            file_path=file.path,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail="File is binary and cannot be displayed as text",
        ) from e

    # Count lines
    has_trailing_newline = content.endswith("\n") if content else True
    line_count = content.count("\n") + (0 if has_trailing_newline else 1)

    return FileContentResponse(
        id=file.id or 0,
        path=file.path,
        language=file.language,
        content=content,
        line_count=line_count,
        size_bytes=len(content.encode("utf-8")),
    )


@router.get("/history", response_model=FileHistoryResponse)
async def get_file_history(
    repo: str,
    path: str,
    repo_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
    commit_adapter: CommitAdapter,
) -> FileHistoryResponse:
    """
    Get the version history of a file (for time travel).

    Query parameters:
    - repo: Repository name
    - path: File path within the repository

    Returns all indexed versions of the file, ordered by commit date (newest first).
    """
    # Validate inputs
    repo = validate_repo_name(repo)
    path = validate_path(path)

    # Get repository by name
    repository = await repo_adapter.find_by_name(repo)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    repository_id = repository.id if repository.id is not None else 0

    # Get all versions of this file
    files = await file_adapter.list_versions_by_path(repository_id, path)
    if not files:
        raise HTTPException(status_code=404, detail="File not found")

    # Get commit info for each version
    versions = []
    for file in files:
        commit_record = await commit_adapter.find_by_id(file.commit_id)
        if commit_record:
            versions.append(
                FileVersionResponse(
                    commit_id=commit_record.id or 0,
                    commit_hash=commit_record.commit_hash.value,
                    short_hash=commit_record.short_hash
                    or commit_record.commit_hash.value[:7],
                    commit_date=(
                        commit_record.commit_date.isoformat()
                        if commit_record.commit_date
                        else ""
                    ),
                    message=(
                        commit_record.message[:100] if commit_record.message else ""
                    ),
                    content_hash=file.content_hash or "",
                )
            )

    return FileHistoryResponse(
        path=path,
        repository_name=repository.name,
        versions=versions,
        total=len(versions),
    )


@router.get("/by-path/symbols", response_model=FileSymbolsResponse)
async def get_file_symbols_by_path(
    repo: str,
    path: str,
    repo_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
    symbol_adapter: SymbolAdapter,
    commit: str | None = None,
) -> FileSymbolsResponse:
    """
    Get symbols for a file by repository name and file path.

    Query parameters:
    - repo: Repository name
    - path: File path within the repository
    - commit: Commit hash (optional, defaults to latest version for time travel)
    """
    # Validate inputs to prevent path traversal and injection
    repo = validate_repo_name(repo)
    path = validate_path(path)

    # Get repository by name
    repository = await repo_adapter.find_by_name(repo)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    repository_id = repository.id if repository.id is not None else 0

    # Get file by repository and path (and optionally commit)
    if commit:
        # Time travel mode: get file at specific commit
        file = await file_adapter.find_by_repository_path_and_commit_hash(
            repository_id, path, commit
        )
        if not file:
            raise HTTPException(
                status_code=404,
                detail=f"File not found at commit {commit}",
            )
    else:
        # Default: get latest version
        file = await file_adapter.find_by_repository_and_path(repository_id, path)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

    file_id = file.id or 0

    # Get symbols in this file
    symbols = await symbol_adapter.list_by_file(file_id)

    return FileSymbolsResponse(
        file_id=file_id,
        file_path=file.path,
        symbols=[
            FileSymbolResponse(
                id=s.id or 0,
                name=s.name,
                qualified_name=s.qualified_name,
                kind=s.kind,
                start_line=s.start_line,
                start_column=s.start_column,
                end_line=s.end_line,
                end_column=s.end_column,
                signature=s.signature,
            )
            for s in symbols
        ],
        total=len(symbols),
    )


@router.get("/by-path/references", response_model=FileReferencesResponse)
async def get_file_references_by_path(
    repo: str,
    path: str,
    repo_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
    ref_adapter: ReferenceAdapter,
    commit: str | None = None,
) -> FileReferencesResponse:
    """
    Get references from a file by repository name and file path.

    Query parameters:
    - repo: Repository name
    - path: File path within the repository
    - commit: Commit hash (optional, defaults to latest version for time travel)
    """
    # Validate inputs to prevent path traversal and injection
    repo = validate_repo_name(repo)
    path = validate_path(path)

    # Get repository by name
    repository = await repo_adapter.find_by_name(repo)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    repository_id = repository.id if repository.id is not None else 0

    # Get file by repository and path (and optionally commit)
    if commit:
        # Time travel mode: get file at specific commit
        file = await file_adapter.find_by_repository_path_and_commit_hash(
            repository_id, path, commit
        )
        if not file:
            raise HTTPException(
                status_code=404,
                detail=f"File not found at commit {commit}",
            )
    else:
        # Default: get latest version
        file = await file_adapter.find_by_repository_and_path(repository_id, path)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

    file_id = file.id or 0

    # Get references from this file
    references = await ref_adapter.list_by_file(file_id)

    return FileReferencesResponse(
        file_id=file_id,
        file_path=file.path,
        references=[
            FileReferenceResponse(
                id=r.id or 0,
                reference_text=r.reference_text,
                reference_type=r.reference_type.value,
                source_line=r.source_line,
                source_column=r.source_column,
                target_symbol_id=r.target_symbol_id,
            )
            for r in references
        ],
        total=len(references),
    )


@router.get("/{file_id}/content", response_model=FileContentResponse)
async def get_file_content(
    file_id: int,
    file_adapter: FileAdapter,
    commit_adapter: CommitAdapter,
    repo_adapter: RepositoryAdapter,
    git_service: GitServiceDep,
) -> FileContentResponse:
    """
    Get the content of a file.

    Fetches file content from the git repository at the indexed commit.
    """
    # Get file info
    file = await file_adapter.find_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Get commit info to get the hash
    commit = await commit_adapter.find_by_id(file.commit_id)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    # Get repository to get the path
    repository = await repo_adapter.find_by_id(file.repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    # The repository URL is the local path for indexed repos
    repo_path = Path(repository.url)
    if not repo_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Repository path not found: {repository.url}",
        )

    # Fetch content from git
    try:
        content = git_service.get_file_content(
            repo_path=repo_path,
            commit_hash=commit.commit_hash.value,
            file_path=file.path,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail="File is binary and cannot be displayed as text",
        ) from e

    # Count lines: number of newlines + 1 if file doesn't end with newline
    has_trailing_newline = content.endswith("\n") if content else True
    line_count = content.count("\n") + (0 if has_trailing_newline else 1)

    return FileContentResponse(
        id=file.id or 0,
        path=file.path,
        language=file.language,
        content=content,
        line_count=line_count,
        size_bytes=len(content.encode("utf-8")),
    )


@router.get("/{file_id}/symbols", response_model=FileSymbolsResponse)
async def get_file_symbols(
    file_id: int,
    file_adapter: FileAdapter,
    symbol_adapter: SymbolAdapter,
) -> FileSymbolsResponse:
    """
    Get all symbols defined in a file.

    Returns symbols with their locations for highlighting in the code viewer.
    """
    # Get file info
    file = await file_adapter.find_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Get symbols in this file
    symbols = await symbol_adapter.list_by_file(file_id)

    return FileSymbolsResponse(
        file_id=file.id or 0,
        file_path=file.path,
        symbols=[
            FileSymbolResponse(
                id=s.id or 0,
                name=s.name,
                qualified_name=s.qualified_name,
                kind=s.kind,
                start_line=s.start_line,
                start_column=s.start_column,
                end_line=s.end_line,
                end_column=s.end_column,
                signature=s.signature,
            )
            for s in symbols
        ],
        total=len(symbols),
    )


@router.get("/{file_id}/references", response_model=FileReferencesResponse)
async def get_file_references(
    file_id: int,
    file_adapter: FileAdapter,
    ref_adapter: ReferenceAdapter,
) -> FileReferencesResponse:
    """
    Get all references from a file.

    Returns references (usages of symbols) with their locations
    for making them clickable in the code viewer.
    """
    # Get file info
    file = await file_adapter.find_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Get references from this file
    references = await ref_adapter.list_by_file(file_id)

    return FileReferencesResponse(
        file_id=file.id or 0,
        file_path=file.path,
        references=[
            FileReferenceResponse(
                id=r.id or 0,
                reference_text=r.reference_text,
                reference_type=r.reference_type.value,
                source_line=r.source_line,
                source_column=r.source_column,
                target_symbol_id=r.target_symbol_id,
            )
            for r in references
        ],
        total=len(references),
    )

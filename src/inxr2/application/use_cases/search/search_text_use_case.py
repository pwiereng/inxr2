"""Text search use case - search across comments, docstrings, commit messages, and non-code files."""

from dataclasses import dataclass

from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    ReferenceRepositoryPort,
    RepositoryPort,
)
from ...ports.services import TextSearchPort, TextSearchQuery


@dataclass(frozen=True)
class SearchTextRequest:
    """Request to search text content.

    Attributes:
        query: Search query string
        mode: Query mode (keyword, phrase, regex) - default: keyword
        repository_id: Optional repository filter
        branch: Optional branch name filter
        commit_hash: Optional commit hash filter (for time travel)
        source_types: Optional list of source types to filter by
        languages: Optional list of languages to filter by
        extensions: Optional list of file extensions to filter by (e.g. [".py", ".ts"])
        case_sensitive: Case-sensitive matching (applies to all modes, default: True)
        scope: Search scope for cross-repo search (default: "latest").
            Only applies when repository_id is not provided.
        limit: Maximum results to return (default: 20)
        offset: Pagination offset (default: 0)
    """

    query: str
    mode: str = "keyword"
    repository_id: int | None = None
    branch: str | None = None
    commit_hash: str | None = None
    source_types: list[str] | None = None
    languages: list[str] | None = None
    extensions: list[str] | None = None
    case_sensitive: bool = True
    scope: str = "latest"
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class SearchTextResultItem:
    """A single text search result.

    Attributes:
        id: Text content ID
        repository_id: Repository ID
        repository_name: Repository name
        file_path: File path (None for commit messages)
        source_line: Start line number
        source_end_line: End line number
        source_type: Source type (comment, docstring, commit_message, file_content)
        content: The searchable text content
        content_type: Content type (single_line_comment, block_comment, etc.)
        language: Programming language
        commit_hash: Commit hash (None for file-derived content without direct commit)
        branch: Branch name (if applicable)
        rank: Relevance score (higher is better)
        headline: Highlighted snippet (optional)
    """

    id: int
    repository_id: int
    repository_name: str
    file_path: str | None
    source_line: int | None
    source_end_line: int | None
    source_type: str
    content: str
    content_type: str | None
    language: str | None
    commit_hash: str | None
    branch: str | None
    rank: float
    headline: str | None


@dataclass(frozen=True)
class SearchTextResponse:
    """Response from text search.

    Attributes:
        results: List of matching text content items
        total: Total number of matches (for pagination)
        query: The search query used
        mode: The query mode used
        limit: The limit used
        offset: The offset used
    """

    results: list[SearchTextResultItem]
    total: int
    query: str
    mode: str
    limit: int
    offset: int


class SearchTextUseCase:
    """Use case for searching text content.

    This use case orchestrates text search by:
    1. Building a TextSearchQuery from the request
    2. Calling the TextSearchPort to execute the search
    3. Hydrating results with repository name, file path, and commit hash
    4. Returning enriched results
    """

    def __init__(
        self,
        text_search: TextSearchPort,
        repository_repo: RepositoryPort,
        commit_repo: CommitRepositoryPort,
        file_repo: FileRepositoryPort,
        reference_repo: ReferenceRepositoryPort | None = None,
    ):
        """Initialize use case.

        Args:
            text_search: Text search port for executing searches
            repository_repo: Repository repository for fetching repository info
            commit_repo: Commit repository for fetching commit info
            file_repo: File repository for fetching file info
            reference_repo: Reference repository for searching references (optional)
        """
        self._text_search = text_search
        self._repository_repo = repository_repo
        self._commit_repo = commit_repo
        self._file_repo = file_repo
        self._reference_repo = reference_repo

    async def execute(self, request: SearchTextRequest) -> SearchTextResponse:
        """Execute text search.

        Args:
            request: Search request parameters

        Returns:
            Search response with enriched results

        Raises:
            ValueError: If query is empty or invalid
        """
        # Convert commit_hash to commit_id if provided
        commit_id = None
        if request.commit_hash and request.repository_id:
            commit = await self._commit_repo.find_by_hash(
                request.repository_id, request.commit_hash
            )
            if commit:
                commit_id = commit.id
            else:
                # Commit hash specified but not found - return empty results
                return SearchTextResponse(
                    results=[],
                    total=0,
                    query=request.query,
                    mode=request.mode,
                    limit=request.limit,
                    offset=request.offset,
                )

        # Separate "reference" from text source types
        has_reference = False
        text_source_types = request.source_types
        if request.source_types and "reference" in request.source_types:
            has_reference = True
            text_source_types = [st for st in request.source_types if st != "reference"]
            if not text_source_types:
                text_source_types = None

        # Determine if we need to run text search
        reference_only = has_reference and text_source_types is None
        run_text_search = not reference_only

        text_results = []
        text_total = 0

        if run_text_search:
            # Build search query
            search_query = TextSearchQuery(
                query=request.query,
                mode=request.mode,
                repository_id=request.repository_id,
                branch=request.branch,
                commit_id=commit_id,
                source_types=text_source_types,
                languages=request.languages,
                extensions=request.extensions,
                case_sensitive=request.case_sensitive,
                scope=request.scope if request.repository_id is None else None,
                limit=request.limit,
                offset=request.offset,
            )

            # Execute search
            raw_results, text_total = await self._text_search.search(search_query)

            # Collect unique IDs for bulk fetching
            repo_ids = {r.text_content.repository_id for r in raw_results}
            file_ids = {
                r.text_content.source_file_id
                for r in raw_results
                if r.text_content.source_file_id is not None
            }
            commit_ids = {
                r.text_content.commit_id
                for r in raw_results
                if r.text_content.commit_id is not None
            }

            # Bulk fetch repositories, files, and commits (single query each)
            repositories = await self._repository_repo.find_by_ids(list(repo_ids))
            repo_map = {r.id: r.name for r in repositories if r.id is not None}

            files = await self._file_repo.find_by_ids(list(file_ids))

            commits = await self._commit_repo.find_by_ids(list(commit_ids))
            commit_map = {c.id: c for c in commits if c.id is not None}

            # Bulk fetch branches for all commits
            branches_map = await self._commit_repo.get_branches_for_commits(
                list(commit_ids)
            )

            # Hydrate results with repository, file, and commit info
            for result in raw_results:
                text_content = result.text_content

                repository_name = repo_map.get(text_content.repository_id, "unknown")

                file_path = None
                if text_content.source_file_id:
                    file = files.get(text_content.source_file_id)
                    if file:
                        file_path = file.path

                commit = (
                    commit_map.get(text_content.commit_id)
                    if text_content.commit_id is not None
                    else None
                )
                commit_hash = commit.commit_hash.value if commit else None

                branch = None
                branches = (
                    branches_map.get(text_content.commit_id, [])
                    if text_content.commit_id is not None
                    else []
                )
                if branches:
                    branch = branches[0]

                if branch is None and request.branch:
                    branch = request.branch

                text_results.append(
                    SearchTextResultItem(
                        id=text_content.id or 0,
                        repository_id=text_content.repository_id,
                        repository_name=repository_name,
                        file_path=file_path,
                        source_line=text_content.source_line,
                        source_end_line=text_content.source_end_line,
                        source_type=text_content.source_type,
                        content=text_content.content,
                        content_type=text_content.content_type,
                        language=text_content.language,
                        commit_hash=commit_hash,
                        branch=branch,
                        rank=result.rank,
                        headline=result.headline,
                    )
                )

        # Reference search
        ref_results: list[SearchTextResultItem] = []
        ref_total = 0

        if has_reference and self._reference_repo is not None:
            # Reference-only: use request pagination directly
            # Mixed: only fetch on first page (offset=0) as supplementary results
            if reference_only:
                ref_limit = request.limit
                ref_offset = request.offset
            else:
                ref_limit = request.limit
                ref_offset = 0

            if reference_only or request.offset == 0:
                scope = request.scope if request.repository_id is None else None
                refs, ref_total = await self._reference_repo.search_by_text(
                    query=request.query,
                    repository_id=request.repository_id,
                    branch=request.branch,
                    scope=scope,
                    extensions=request.extensions,
                    limit=ref_limit,
                    offset=ref_offset,
                    mode=request.mode,
                    case_sensitive=request.case_sensitive,
                )

                if refs:
                    # Hydrate reference results with file paths and repo names
                    ref_repo_ids = {r.repository_id for r in refs}
                    ref_file_ids = {r.source_file_id for r in refs}

                    ref_repositories = await self._repository_repo.find_by_ids(
                        list(ref_repo_ids)
                    )
                    ref_repo_map = {
                        r.id: r.name for r in ref_repositories if r.id is not None
                    }

                    ref_files = await self._file_repo.find_by_ids(list(ref_file_ids))

                    for ref in refs:
                        repository_name = ref_repo_map.get(ref.repository_id, "unknown")
                        file_path = None
                        language = None
                        file = ref_files.get(ref.source_file_id)
                        if file:
                            file_path = file.path
                            language = file.language

                        ref_results.append(
                            SearchTextResultItem(
                                id=ref.id or 0,
                                repository_id=ref.repository_id,
                                repository_name=repository_name,
                                file_path=file_path,
                                source_line=ref.source_line,
                                source_end_line=ref.source_line,
                                source_type="reference",
                                content=ref.reference_text,
                                content_type=ref.reference_type.value,
                                language=language,
                                commit_hash=None,
                                branch=request.branch,
                                rank=1.0,
                                headline=None,
                            )
                        )

        # Combine results
        all_results = ref_results + text_results

        # Pagination total: reference-only uses ref_total, mixed uses text_total
        if reference_only:
            total = ref_total
        else:
            total = text_total

        return SearchTextResponse(
            results=all_results,
            total=total,
            query=request.query,
            mode=request.mode,
            limit=request.limit,
            offset=request.offset,
        )

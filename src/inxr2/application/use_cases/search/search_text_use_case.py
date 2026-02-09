"""Text search use case - search across comments, docstrings, commit messages, and non-code files."""

from dataclasses import dataclass

from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
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
        commit_hash: Commit hash
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
    commit_hash: str
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
    ):
        """Initialize use case.

        Args:
            text_search: Text search port for executing searches
            repository_repo: Repository repository for fetching repository info
            commit_repo: Commit repository for fetching commit info
            file_repo: File repository for fetching file info
        """
        self._text_search = text_search
        self._repository_repo = repository_repo
        self._commit_repo = commit_repo
        self._file_repo = file_repo

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

        # Build search query
        search_query = TextSearchQuery(
            query=request.query,
            mode=request.mode,
            repository_id=request.repository_id,
            branch=request.branch,
            commit_id=commit_id,
            source_types=request.source_types,
            languages=request.languages,
            limit=request.limit,
            offset=request.offset,
        )

        # Execute search
        results, total = await self._text_search.search(search_query)

        # Collect unique IDs for bulk fetching
        repo_ids = {r.text_content.repository_id for r in results}
        file_ids = {
            r.text_content.source_file_id
            for r in results
            if r.text_content.source_file_id is not None
        }
        commit_ids = {r.text_content.commit_id for r in results}

        # Bulk fetch repositories, files, and commits (single query each)
        repositories = await self._repository_repo.find_by_ids(list(repo_ids))
        repo_map = {r.id: r.name for r in repositories if r.id is not None}

        files = await self._file_repo.find_by_ids(list(file_ids))
        # files is already a dict[int, File]

        commits = await self._commit_repo.find_by_ids(list(commit_ids))
        commit_map = {c.id: c for c in commits if c.id is not None}

        # Bulk fetch branches for all commits
        branches_map = await self._commit_repo.get_branches_for_commits(
            list(commit_ids)
        )

        # Hydrate results with repository, file, and commit info
        enriched_results = []
        for result in results:
            text_content = result.text_content

            # Get repository name from bulk-fetched data
            repository_name = repo_map.get(text_content.repository_id, "unknown")

            # Get file path from bulk-fetched data
            file_path = None
            if text_content.source_file_id:
                file = files.get(text_content.source_file_id)
                if file:
                    file_path = file.path

            # Get commit hash from bulk-fetched data
            commit = commit_map.get(text_content.commit_id)
            commit_hash = commit.commit_hash.value if commit else "unknown"

            # Get branch from bulk-fetched data
            # Note: A commit can be on multiple branches, we'll take the first one
            branch = None
            branches = branches_map.get(text_content.commit_id, [])
            if branches:
                branch = branches[0]

            enriched_results.append(
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

        return SearchTextResponse(
            results=enriched_results,
            total=total,
            query=request.query,
            mode=request.mode,
            limit=request.limit,
            offset=request.offset,
        )

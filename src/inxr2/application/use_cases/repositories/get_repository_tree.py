"""Get repository file tree use case."""

from dataclasses import dataclass, field

from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    RepositoryPort,
)


@dataclass
class TreeNode:
    """A node in the file tree (file or directory)."""

    name: str
    path: str
    node_type: str  # "file" or "directory"
    file_id: int | None = None
    language: str | None = None
    children: list["TreeNode"] = field(default_factory=list)


@dataclass
class GetRepositoryTreeRequest:
    """Request to get repository file tree."""

    repository_id: int | None = None
    repository_name: str | None = None
    commit_hash: str | None = None  # For time travel: get tree at specific commit
    branch: str | None = None  # For branch filtering: resolves to latest indexed commit

    def __post_init__(self) -> None:
        if self.repository_id is None and self.repository_name is None:
            raise ValueError("Either repository_id or repository_name must be provided")


@dataclass
class GetRepositoryTreeResponse:
    """Response containing repository file tree."""

    repository_id: int
    repository_name: str
    root: list[TreeNode]
    total_files: int
    total_directories: int


class GetRepositoryTreeUseCase:
    """Use case for getting repository file tree structure."""

    def __init__(
        self,
        repository_repo: RepositoryPort,
        file_repo: FileRepositoryPort,
        commit_repo: CommitRepositoryPort | None = None,
    ) -> None:
        """
        Initialize use case.

        Args:
            repository_repo: Repository for accessing repository entities
            file_repo: Repository for accessing file entities
            commit_repo: Repository for accessing commit entities (for time travel)
        """
        self._repository_repo = repository_repo
        self._file_repo = file_repo
        self._commit_repo = commit_repo

    async def execute(
        self, request: GetRepositoryTreeRequest
    ) -> GetRepositoryTreeResponse:
        """
        Execute repository tree retrieval.

        Args:
            request: Request with repository identifier and optional commit_hash

        Returns:
            Tree structure of files and directories

        Raises:
            ValueError: If repository not found
        """
        # Get repository
        if request.repository_id is not None:
            repository = await self._repository_repo.find_by_id(request.repository_id)
        else:
            repository = await self._repository_repo.find_by_name(
                request.repository_name or ""
            )

        if not repository:
            raise ValueError("Repository not found")

        repository_id = repository.id if repository.id is not None else 0

        # Resolve commit: explicit commit_hash > branch resolution > latest
        resolved_commit_hash = request.commit_hash
        if not resolved_commit_hash and request.branch:
            # Resolve branch to latest indexed commit
            if not self._commit_repo:
                raise ValueError(
                    "Branch resolution requires commit repository. "
                    "branch was provided but commit_repo is not available."
                )
            branch_commit = await self._commit_repo.find_latest_by_branch(
                repository_id, request.branch
            )
            if branch_commit:
                resolved_commit_hash = branch_commit.commit_hash.value
            elif request.branch != repository.default_branch:
                # Branch has no indexed commits (e.g., merged branch with delta indexing)
                # Fall back to default branch
                branch_commit = await self._commit_repo.find_latest_by_branch(
                    repository_id, repository.default_branch
                )
                if branch_commit:
                    resolved_commit_hash = branch_commit.commit_hash.value

        # Get files - either at specific commit (time travel) or latest
        if resolved_commit_hash:
            # Time travel requested - commit_repo is required
            if not self._commit_repo:
                raise ValueError(
                    "Time travel requires commit repository. "
                    "commit_hash was provided but commit_repo is not available."
                )
            # Get files at specific commit
            commit = await self._commit_repo.find_by_hash(
                repository_id, resolved_commit_hash
            )
            if not commit or commit.id is None:
                raise ValueError(f"Commit not found: {resolved_commit_hash}")
            files = await self._file_repo.list_by_commit(commit.id)
        else:
            # Default: get latest files
            files = await self._file_repo.list_by_repository(repository_id)

        # Build tree structure
        tree_dict: dict[str, TreeNode] = {}
        root_nodes: list[TreeNode] = []
        total_dirs = 0

        for file in files:
            parts = file.path.split("/")
            current_path = ""

            for i, part in enumerate(parts):
                parent_path = current_path
                current_path = f"{current_path}/{part}" if current_path else part
                is_file = i == len(parts) - 1

                if current_path not in tree_dict:
                    node = TreeNode(
                        name=part,
                        path=current_path,
                        node_type="file" if is_file else "directory",
                        file_id=file.id if is_file else None,
                        language=file.language if is_file else None,
                        children=[],
                    )
                    tree_dict[current_path] = node

                    if not is_file:
                        total_dirs += 1

                    if parent_path:
                        parent_node = tree_dict.get(parent_path)
                        if parent_node:
                            parent_node.children.append(node)
                    else:
                        root_nodes.append(node)

        # Sort nodes: directories first, then files, alphabetically
        root_nodes = self._sort_nodes(root_nodes)

        return GetRepositoryTreeResponse(
            repository_id=repository_id,
            repository_name=repository.name,
            root=root_nodes,
            total_files=len(files),
            total_directories=total_dirs,
        )

    def _sort_nodes(self, nodes: list[TreeNode]) -> list[TreeNode]:
        """Sort nodes: directories first, then files, alphabetically."""
        dirs = [n for n in nodes if n.node_type == "directory"]
        files = [n for n in nodes if n.node_type == "file"]
        dirs = sorted(dirs, key=lambda x: x.name)
        files = sorted(files, key=lambda x: x.name)
        for d in dirs:
            d.children = self._sort_nodes(d.children)
        return dirs + files

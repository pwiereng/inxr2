"""Get repository file tree use case."""

from dataclasses import dataclass, field
from pathlib import Path

from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    RepositoryPort,
)
from ...ports.services import GitServicePort


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
    changed_only: bool = (
        False  # Only show files changed at the commit (requires commit_hash)
    )

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
        git_service: GitServicePort | None = None,
    ) -> None:
        """
        Initialize use case.

        Args:
            repository_repo: Repository for accessing repository entities
            file_repo: Repository for accessing file entities
            commit_repo: Repository for accessing commit entities (for time travel)
            git_service: Git service for determining changed files (for changed_only)
        """
        self._repository_repo = repository_repo
        self._file_repo = file_repo
        self._commit_repo = commit_repo
        self._git_service = git_service

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

        # Get files based on request parameters:
        # 1. Explicit commit_hash with changed_only: get only files changed at that commit
        # 2. Explicit commit_hash: get full tree state at that commit
        # 3. Branch specified: get latest version of each file on that branch
        # 4. Default: get latest files across all branches
        if request.commit_hash:
            # Time travel to specific commit
            if not self._commit_repo:
                raise ValueError(
                    "Time travel requires commit repository. "
                    "commit_hash was provided but commit_repo is not available."
                )
            commit = await self._commit_repo.find_by_hash(
                repository_id, request.commit_hash
            )
            if not commit or commit.id is None:
                raise ValueError(f"Commit not found: {request.commit_hash}")

            if request.changed_only:
                # Use git to determine which files changed at this commit
                # (compares against first parent — correct for merges)
                if not self._git_service:
                    raise ValueError(
                        "changed_only requires git_service to determine changed files."
                    )
                repo_path = Path(repository.url)
                changed = self._git_service.get_changed_files_in_commit(
                    repo_path, request.commit_hash
                )
                changed_paths = set(changed.added + changed.modified)

                # Get full tree at this commit, then filter to changed paths
                all_files = await self._file_repo.list_at_or_before_commit(
                    repository_id, commit.id
                )
                files = [f for f in all_files if f.path in changed_paths]
            else:
                # Get the latest version of each file at or before this commit
                # This returns the full tree state, not just files changed at this commit
                files = await self._file_repo.list_at_or_before_commit(
                    repository_id, commit.id
                )
        elif request.branch:
            # Get latest version of each file on the branch
            # This aggregates across all commits on the branch
            files = await self._file_repo.list_latest_by_branch(
                repository_id, request.branch
            )
            if not files:
                # Branch has no indexed files
                raise ValueError(
                    f"Branch '{request.branch}' has no indexed files. "
                    f"Try the default branch '{repository.default_branch}' or "
                    f"remove the branch parameter to use the latest indexed version."
                )
        else:
            # Default: get latest files across all branches
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

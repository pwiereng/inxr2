"""
Git service adapter using GitPython.

Provides git operations for indexing repositories.
"""

import logging
from pathlib import Path
from typing import Any

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

logger = logging.getLogger(__name__)


class GitService:
    """
    Git operations service using GitPython.

    Provides methods for repository analysis, commit tracking,
    and file content retrieval needed for indexing.
    """

    def get_repository_info(self, repo_path: Path) -> dict[str, Any]:
        """
        Get basic repository information.

        Args:
            repo_path: Path to the git repository

        Returns:
            Dictionary with repository info:
                - name: Repository name (from directory)
                - url: Remote URL (if available)
                - current_branch: Current branch name
                - is_bare: Whether repo is bare
        """
        try:
            repo = Repo(repo_path)

            # Get remote URL if available
            url = None
            if repo.remotes:
                try:
                    url = repo.remotes.origin.url
                except AttributeError:
                    # No origin remote
                    url = repo.remotes[0].url if repo.remotes else None

            # Get current branch
            try:
                current_branch = repo.active_branch.name
            except TypeError:
                # Detached HEAD state
                current_branch = None

            return {
                "name": repo_path.name,
                "url": url,
                "current_branch": current_branch,
                "is_bare": repo.bare,
            }

        except InvalidGitRepositoryError as e:
            raise ValueError(f"Not a valid git repository: {repo_path}") from e

    def get_current_commit(self, repo_path: Path, branch: str | None = None) -> str:
        """
        Get the current HEAD commit hash.

        Args:
            repo_path: Path to the git repository
            branch: Branch name (optional, uses HEAD if not specified)

        Returns:
            Full 40-character commit hash
        """
        repo = Repo(repo_path)

        if branch:
            try:
                commit = repo.commit(branch)
            except Exception:
                # Branch might be a remote tracking branch
                try:
                    commit = repo.commit(f"origin/{branch}")
                except Exception:
                    commit = repo.head.commit
        else:
            commit = repo.head.commit

        return commit.hexsha

    def get_commit_info(self, repo_path: Path, commit_hash: str) -> dict[str, Any]:
        """
        Get detailed information about a commit.

        Args:
            repo_path: Path to the git repository
            commit_hash: Full or short commit hash

        Returns:
            Dictionary with commit info:
                - hash: Full commit hash
                - short_hash: Short (7-char) hash
                - author_name, author_email, author_date
                - committer_name, committer_email, commit_date
                - message: Commit message
                - parent_hashes: List of parent commit hashes
        """
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)

        return {
            "hash": commit.hexsha,
            "short_hash": commit.hexsha[:7],
            "author_name": commit.author.name,
            "author_email": commit.author.email,
            "author_date": commit.authored_datetime,
            "committer_name": commit.committer.name,
            "committer_email": commit.committer.email,
            "commit_date": commit.committed_datetime,
            "message": commit.message.strip(),
            "parent_hashes": [p.hexsha for p in commit.parents],
        }

    def get_commits_since(
        self,
        repo_path: Path,
        since_commit: str,
        branch: str | None = None,
        max_count: int = 1000,
    ) -> list[str]:
        """
        Get list of commit hashes since a given commit.

        Args:
            repo_path: Path to the git repository
            since_commit: Commit hash to start from (exclusive)
            branch: Branch to traverse (optional)
            max_count: Maximum number of commits to return

        Returns:
            List of commit hashes (newest first)
        """
        repo = Repo(repo_path)

        try:
            # Get commits between since_commit and HEAD (or branch)
            rev = branch if branch else "HEAD"
            commits = list(
                repo.iter_commits(
                    f"{since_commit}..{rev}",
                    max_count=max_count,
                )
            )
            return [c.hexsha for c in commits]
        except GitCommandError:
            # since_commit might not exist, return all commits
            commits = list(repo.iter_commits(rev, max_count=max_count))
            return [c.hexsha for c in commits]

    def get_changed_files(
        self,
        repo_path: Path,
        from_commit: str,
        to_commit: str,
    ) -> dict[str, list[str]]:
        """
        Get files changed between two commits.

        Args:
            repo_path: Path to the git repository
            from_commit: Starting commit hash
            to_commit: Ending commit hash

        Returns:
            Dictionary with:
                - added: List of added file paths
                - modified: List of modified file paths
                - deleted: List of deleted file paths
        """
        repo = Repo(repo_path)

        try:
            from_c = repo.commit(from_commit)
            to_c = repo.commit(to_commit)
        except Exception as e:
            raise ValueError(f"Invalid commit hash: {e}") from e

        diff = from_c.diff(to_c)

        added: list[str] = []
        modified: list[str] = []
        deleted: list[str] = []

        for d in diff:
            if d.new_file and d.b_path:
                added.append(d.b_path)
            elif d.deleted_file and d.a_path:
                deleted.append(d.a_path)
            elif d.renamed_file:
                if d.a_path:
                    deleted.append(d.a_path)
                if d.b_path:
                    added.append(d.b_path)
            elif d.b_path or d.a_path:
                modified.append(d.b_path or d.a_path or "")

        return {
            "added": added,
            "modified": modified,
            "deleted": deleted,
        }

    def list_files(
        self,
        repo_path: Path,
        commit_hash: str,
        patterns: list[str] | None = None,
    ) -> list[str]:
        """
        List all files in the repository at a specific commit.

        Args:
            repo_path: Path to the git repository
            commit_hash: Commit hash to list files at
            patterns: Optional list of glob patterns to filter files

        Returns:
            List of file paths (relative to repo root)
        """
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)

        files: list[str] = []

        def traverse_tree(tree: Any, prefix: str = "") -> None:
            for item in tree:
                path = f"{prefix}{item.name}" if prefix else item.name
                if item.type == "blob":
                    files.append(path)
                elif item.type == "tree":
                    traverse_tree(item, f"{path}/")

        traverse_tree(commit.tree)

        # Filter by patterns if specified
        if patterns:
            from fnmatch import fnmatch

            files = [
                f for f in files if any(fnmatch(f, pattern) for pattern in patterns)
            ]

        return sorted(files)

    def get_file_content(
        self,
        repo_path: Path,
        commit_hash: str,
        file_path: str,
    ) -> str:
        """
        Get the content of a file at a specific commit.

        Args:
            repo_path: Path to the git repository
            commit_hash: Commit hash
            file_path: Path to file (relative to repo root)

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist at commit
            UnicodeDecodeError: If file is binary
        """
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)

        try:
            # Navigate to the file blob
            blob = commit.tree / file_path
            content = blob.data_stream.read()

            # Try to decode as UTF-8
            try:
                return str(content.decode("utf-8"))
            except UnicodeDecodeError:
                # Try other encodings
                for encoding in ["latin-1", "cp1252"]:
                    try:
                        return str(content.decode(encoding))
                    except UnicodeDecodeError:
                        continue
                # If all fail, raise
                raise

        except KeyError as e:
            raise FileNotFoundError(
                f"File not found at commit {commit_hash[:8]}: {file_path}"
            ) from e

    def is_binary_file(self, repo_path: Path, commit_hash: str, file_path: str) -> bool:
        """
        Check if a file is binary.

        Args:
            repo_path: Path to the git repository
            commit_hash: Commit hash
            file_path: Path to file (relative to repo root)

        Returns:
            True if file is binary, False otherwise
        """
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)

        try:
            blob = commit.tree / file_path
            # Check for null bytes in first 8KB
            content = blob.data_stream.read(8192)
            return b"\x00" in content
        except KeyError:
            return False

    def get_file_hash(self, repo_path: Path, commit_hash: str, file_path: str) -> str:
        """
        Get the git blob hash for a file.

        This can be used to detect unchanged files between commits.

        Args:
            repo_path: Path to the git repository
            commit_hash: Commit hash
            file_path: Path to file (relative to repo root)

        Returns:
            Git blob SHA-1 hash
        """
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)

        try:
            blob = commit.tree / file_path
            return blob.hexsha
        except KeyError as e:
            raise FileNotFoundError(f"File not found: {file_path}") from e

    def list_commits(
        self,
        repo_path: Path,
        branch: str,
        max_count: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        List commits for a branch, from oldest to newest.

        Args:
            repo_path: Path to the git repository
            branch: Branch name to list commits for
            max_count: Maximum number of commits to return

        Returns:
            List of commit info dicts (oldest first), each containing:
                - hash: Full 40-char commit hash
                - short_hash: 7-char hash
                - author_name, author_email, author_date
                - committer_name, committer_email, commit_date
                - message: Commit message
                - parent_hashes: List of parent commit hashes
        """
        repo = Repo(repo_path)

        try:
            # Try local branch first
            commits = list(repo.iter_commits(branch, max_count=max_count))
        except Exception:
            # Try remote tracking branch
            try:
                commits = list(
                    repo.iter_commits(f"origin/{branch}", max_count=max_count)
                )
            except Exception as e:
                logger.warning(f"Could not find branch {branch}: {e}")
                return []

        # iter_commits returns newest first, reverse to get oldest first
        commits = list(reversed(commits))

        return [
            {
                "hash": c.hexsha,
                "short_hash": c.hexsha[:7],
                "author_name": c.author.name,
                "author_email": c.author.email,
                "author_date": c.authored_datetime,
                "committer_name": c.committer.name,
                "committer_email": c.committer.email,
                "commit_date": c.committed_datetime,
                "message": c.message.strip(),
                "parent_hashes": [p.hexsha for p in c.parents],
            }
            for c in commits
        ]

    def get_files_at_commit(
        self,
        repo_path: Path,
        commit_hash: str,
    ) -> set[str]:
        """
        Get the set of all file paths that exist at a specific commit.

        Args:
            repo_path: Path to the git repository
            commit_hash: Commit hash

        Returns:
            Set of file paths (relative to repo root)
        """
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)

        files: set[str] = set()

        def traverse_tree(tree: Any, prefix: str = "") -> None:
            for item in tree:
                path = f"{prefix}{item.name}" if prefix else item.name
                if item.type == "blob":
                    files.add(path)
                elif item.type == "tree":
                    traverse_tree(item, f"{path}/")

        traverse_tree(commit.tree)
        return files

    def get_changed_files_in_commit(
        self,
        repo_path: Path,
        commit_hash: str,
    ) -> dict[str, list[str]]:
        """
        Get files changed in a single commit (vs its parent).

        Args:
            repo_path: Path to the git repository
            commit_hash: Commit hash

        Returns:
            Dictionary with:
                - added: List of added file paths
                - modified: List of modified file paths
                - deleted: List of deleted file paths
        """
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)

        added: list[str] = []
        modified: list[str] = []
        deleted: list[str] = []

        if not commit.parents:
            # Initial commit - all files are "added"
            added = self.list_files(repo_path, commit_hash)
            return {"added": added, "modified": modified, "deleted": deleted}

        # Compare with first parent
        parent = commit.parents[0]
        diff = parent.diff(commit)

        for d in diff:
            if d.new_file and d.b_path:
                added.append(d.b_path)
            elif d.deleted_file and d.a_path:
                deleted.append(d.a_path)
            elif d.renamed_file:
                if d.a_path:
                    deleted.append(d.a_path)
                if d.b_path:
                    added.append(d.b_path)
            elif d.b_path or d.a_path:
                modified.append(d.b_path or d.a_path or "")

        return {"added": added, "modified": modified, "deleted": deleted}

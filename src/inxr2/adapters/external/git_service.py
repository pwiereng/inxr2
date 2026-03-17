"""
Git service adapter using GitPython.

Provides git operations for indexing repositories.
"""

import logging
from pathlib import Path
from typing import Any

from git import Repo
from git.exc import BadName, GitCommandError, InvalidGitRepositoryError, NoSuchPathError

from ...application.ports.services import (
    BlameLineInfo,
    ChangedFiles,
    CommitInfo,
    GitServicePort,
    RenameInfo,
    RepositoryInfo,
)
from ...domain.exceptions import (
    CommitNotFound,
    GitOperationError,
    InvalidRepositoryPath,
)

logger = logging.getLogger(__name__)


class GitService(GitServicePort):
    """
    Git operations service using GitPython.

    Provides methods for repository analysis, commit tracking,
    and file content retrieval needed for indexing.
    """

    def __init__(self) -> None:
        # Bounded cache: typically only a handful of repos are indexed at once.
        # Call clear_repo_cache() to release resources when done.
        self._repo_cache: dict[str, Repo] = {}

    def _get_repo(self, repo_path: Path) -> Repo:
        """Get or create a cached Repo object for the given path.

        Raises:
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        key = str(repo_path)
        if key not in self._repo_cache:
            try:
                self._repo_cache[key] = Repo(key)
            except (InvalidGitRepositoryError, NoSuchPathError) as e:
                raise InvalidRepositoryPath(str(repo_path)) from e
        return self._repo_cache[key]

    def clear_repo_cache(self) -> None:
        """Release all cached Repo instances (call after indexing runs)."""
        self._repo_cache.clear()

    def get_repository_info(self, repo_path: Path) -> RepositoryInfo:
        """
        Get basic repository information.

        Args:
            repo_path: Path to the git repository

        Returns:
            RepositoryInfo with name, url, current_branch, is_bare
        """
        repo = self._get_repo(repo_path)

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

        return RepositoryInfo(
            name=repo_path.name,
            url=url,
            current_branch=current_branch,
            is_bare=repo.bare,
        )

    def get_current_commit(self, repo_path: Path, branch: str | None = None) -> str:
        """
        Get the current HEAD commit hash.

        Args:
            repo_path: Path to the git repository
            branch: Branch name (optional, uses HEAD if not specified)

        Returns:
            Full 40-character commit hash
        """
        repo = self._get_repo(repo_path)

        if branch:
            try:
                commit = repo.commit(branch)
            except (GitCommandError, BadName):
                # Branch might be a remote tracking branch
                try:
                    commit = repo.commit(f"origin/{branch}")
                except (GitCommandError, BadName):
                    commit = repo.head.commit
        else:
            commit = repo.head.commit

        return commit.hexsha

    def get_commit_info(self, repo_path: Path, commit_hash: str) -> CommitInfo:
        """
        Get detailed information about a commit.

        Args:
            repo_path: Path to the git repository
            commit_hash: Full or short commit hash

        Returns:
            CommitInfo with full commit metadata

        Raises:
            CommitNotFound: If the commit hash cannot be resolved.
            GitOperationError: If the git operation fails.
        """
        repo = self._get_repo(repo_path)
        try:
            commit = repo.commit(commit_hash)
        except (BadName, ValueError) as e:
            raise CommitNotFound(commit_hash=commit_hash) from e
        except GitCommandError as e:
            raise GitOperationError("get_commit_info", str(e)) from e

        message = commit.message
        if isinstance(message, bytes):
            message = message.decode("utf-8", errors="replace")

        return CommitInfo(
            hash=commit.hexsha,
            short_hash=commit.hexsha[:7],
            author_name=commit.author.name or "",
            author_email=commit.author.email or "",
            author_date=commit.authored_datetime,
            committer_name=commit.committer.name or "",
            committer_email=commit.committer.email or "",
            commit_date=commit.committed_datetime,
            message=message.strip(),
            parent_hashes=[p.hexsha for p in commit.parents],
        )

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
        repo = self._get_repo(repo_path)

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
        repo = self._get_repo(repo_path)

        try:
            from_c = repo.commit(from_commit)
        except (BadName, ValueError) as e:
            raise CommitNotFound(commit_hash=from_commit) from e
        except GitCommandError as e:
            raise GitOperationError("get_changed_files", str(e)) from e

        try:
            to_c = repo.commit(to_commit)
        except (BadName, ValueError) as e:
            raise CommitNotFound(commit_hash=to_commit) from e
        except GitCommandError as e:
            raise GitOperationError("get_changed_files", str(e)) from e

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
                path = d.b_path or d.a_path
                if path:
                    modified.append(path)

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
        repo = self._get_repo(repo_path)
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

    def list_files_with_hashes(
        self,
        repo_path: Path,
        commit_hash: str,
    ) -> dict[str, str]:
        """List all files with their git blob hashes at a specific commit."""
        repo = self._get_repo(repo_path)
        commit = repo.commit(commit_hash)

        result: dict[str, str] = {}

        def traverse_tree(tree: Any, prefix: str = "") -> None:
            for item in tree:
                path = f"{prefix}{item.name}" if prefix else item.name
                if item.type == "blob":
                    result[path] = item.hexsha
                elif item.type == "tree":
                    traverse_tree(item, f"{path}/")

        traverse_tree(commit.tree)

        return result

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
        repo = self._get_repo(repo_path)
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

    def get_file_raw_content(
        self,
        repo_path: Path,
        commit_hash: str,
        file_path: str,
    ) -> bytes:
        """
        Get the raw bytes of a file at a specific commit.

        Args:
            repo_path: Path to the git repository
            commit_hash: Commit hash
            file_path: Path to file (relative to repo root)

        Returns:
            Raw file content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist at commit
        """
        repo = self._get_repo(repo_path)
        commit = repo.commit(commit_hash)

        try:
            blob = commit.tree / file_path
            return bytes(blob.data_stream.read())
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
        repo = self._get_repo(repo_path)
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
        repo = self._get_repo(repo_path)
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
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]:
        """
        List commits for a branch, from oldest to newest.

        Args:
            repo_path: Path to the git repository
            branch: Branch name to list commits for
            max_count: Maximum number of commits to return (None = all commits)
            since_days: Limit to commits reachable from the last N days of the
                first-parent chain.  All commits reachable from that windowed
                portion of history are included — including merged feature branch
                commits whose individual commit dates predate the cutoff.

        Returns:
            List of CommitInfo (oldest first)
        """
        from datetime import UTC, datetime, timedelta

        repo = self._get_repo(repo_path)

        # Resolve the branch ref (local or origin/).
        rev: str
        try:
            repo.commit(branch)
            rev = branch
        except (GitCommandError, BadName):
            rev = f"origin/{branch}"
            try:
                repo.commit(rev)
            except (GitCommandError, BadName) as e:
                logger.warning(f"Could not find branch {branch}: {e}")
                return []

        if since_days is not None:
            since_date = datetime.now(UTC) - timedelta(days=since_days)
            # Strategy: walk the first-parent chain to find the oldest
            # commit WITHIN the window, then do a bounded full-DAG
            # traversal from that point forward.
            #
            # We cannot use git --since for date filtering because it
            # prunes entire DAG sub-graphs when it hits a commit older
            # than the cutoff.  This silently drops merged feature branch
            # commits whose individual commits predate the window even
            # though the merge commit is recent.  (issue #338)
            #
            # Walking first-parent only first is O(commits_in_window) and
            # avoids scanning unbounded history for large repositories.
            boundary_hash: str | None = None
            for fp_commit in repo.iter_commits(rev, first_parent=True):
                if fp_commit.committed_datetime < since_date:
                    # fp_commit is the first first-parent commit OUTSIDE
                    # the window.  Use it as exclusive lower bound.
                    boundary_hash = fp_commit.hexsha
                    break

            full_rev = f"{boundary_hash}..{rev}" if boundary_hash else rev
            iter_kwargs: dict[str, Any] = {}
            if max_count is not None:
                iter_kwargs["max_count"] = max_count
            commits = list(repo.iter_commits(full_rev, **iter_kwargs))
        else:
            iter_kwargs = {}
            if max_count is not None:
                iter_kwargs["max_count"] = max_count
            commits = list(repo.iter_commits(rev, **iter_kwargs))

        # iter_commits returns newest first, reverse to get oldest first
        commits = list(reversed(commits))

        return self._commits_to_info(commits)

    def get_merge_base(
        self,
        repo_path: Path,
        branch1: str,
        branch2: str,
    ) -> str | None:
        """
        Find the merge-base (common ancestor) of two branches.

        Args:
            repo_path: Path to the git repository
            branch1: First branch name
            branch2: Second branch name

        Returns:
            Commit hash of the merge-base, or None if no common ancestor
        """
        repo = self._get_repo(repo_path)

        def resolve_branch(branch: str) -> Any:
            """Resolve branch name to commit, trying local then remote."""
            try:
                return repo.commit(branch)
            except (GitCommandError, BadName):
                try:
                    return repo.commit(f"origin/{branch}")
                except (GitCommandError, BadName):
                    return None

        commit1 = resolve_branch(branch1)
        commit2 = resolve_branch(branch2)

        if commit1 is None or commit2 is None:
            return None

        try:
            # Use git merge-base command
            merge_bases = repo.merge_base(commit1, commit2)
            if merge_bases:
                return merge_bases[0].hexsha
            return None
        except GitCommandError as e:
            logger.warning(
                f"Could not find merge-base for {branch1} and {branch2}: {e}"
            )
            return None

    def list_branch_commits(
        self,
        repo_path: Path,
        branch: str,
        base_branch: str,
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]:
        """
        List commits that were made on a branch (from creation to merge/HEAD).

        For unmerged branches: commits on branch but not on base_branch.
        For merged branches: finds the merge commit and returns the commits
        that were originally made on the branch.

        Args:
            repo_path: Path to the git repository
            branch: Branch to list commits for
            base_branch: Base branch to compare against (e.g., main)
            max_count: Maximum number of commits to return
            since_days: Only include commits from the last N days (None = no date filter)

        Returns:
            List of CommitInfo (oldest first)
        """
        repo = self._get_repo(repo_path)

        def resolve_branch_ref(b: str) -> str | None:
            """Resolve branch name to a git ref string, trying local then remote."""
            try:
                repo.commit(b)
                return b
            except (GitCommandError, BadName):
                remote = f"origin/{b}"
                try:
                    repo.commit(remote)
                    return remote
                except (GitCommandError, BadName):
                    return None

        branch_ref = resolve_branch_ref(branch)
        base_ref = resolve_branch_ref(base_branch)

        if branch_ref is None:
            return []
        if base_ref is None:
            # No base branch, return all commits on branch
            return self.list_commits(repo_path, branch, max_count, since_days)

        branch_commit = repo.commit(branch_ref)

        # First, try simple case: commits on branch not in base
        merge_base = self.get_merge_base(repo_path, branch, base_branch)
        if merge_base is None:
            return self.list_commits(repo_path, branch, max_count, since_days)

        # Check if branch has unmerged commits
        try:
            unmerged = list(repo.iter_commits(f"{base_ref}..{branch_ref}", max_count=1))
            if unmerged:
                # Branch has unmerged commits - return them
                from datetime import UTC, datetime, timedelta

                iter_kwargs: dict[str, Any] = {}
                if max_count is not None:
                    iter_kwargs["max_count"] = max_count
                if since_days is not None:
                    since_date = datetime.now(UTC) - timedelta(days=since_days)
                    iter_kwargs["since"] = since_date.strftime("%Y-%m-%d")
                commits = list(
                    repo.iter_commits(f"{merge_base}..{branch_ref}", **iter_kwargs)
                )
                commits = list(reversed(commits))
                return self._commits_to_info(commits)
        except GitCommandError as e:
            # Best-effort detection of unmerged commits failed; fall back to
            # merge-commit analysis below instead of failing the entire operation.
            logger.debug(
                "Failed to determine unmerged commits for branch '%s' against "
                "base '%s' in repository '%s': %s",
                branch,
                base_branch,
                repo_path,
                e,
            )

        # Branch appears to be merged - find the merge commit and original branch commits
        # Look for merge commits on base_branch that mention this branch
        try:
            # Search recent merge commits for one that merged this branch
            for merge_candidate in repo.iter_commits(base_ref, max_count=200):
                if len(merge_candidate.parents) == 2:
                    # This is a merge commit - check if it merged our branch
                    # The second parent is typically the merged branch
                    merged_branch_head = merge_candidate.parents[1]

                    # Check if this merge brought in our branch
                    if merged_branch_head.hexsha == branch_commit.hexsha:
                        # Found the merge! Get commits from merge-base to branch head
                        main_before_merge = merge_candidate.parents[0]
                        original_merge_base = repo.merge_base(
                            main_before_merge, merged_branch_head
                        )
                        if original_merge_base:
                            from datetime import UTC, datetime, timedelta

                            iter_kwargs = {}
                            if max_count is not None:
                                iter_kwargs["max_count"] = max_count
                            if since_days is not None:
                                since_date = datetime.now(UTC) - timedelta(
                                    days=since_days
                                )
                                iter_kwargs["since"] = since_date.strftime("%Y-%m-%d")
                            commits = list(
                                repo.iter_commits(
                                    f"{original_merge_base[0].hexsha}..{merged_branch_head.hexsha}",
                                    **iter_kwargs,
                                )
                            )
                            commits = list(reversed(commits))
                            return self._commits_to_info(commits)
        except GitCommandError as e:
            logger.warning(f"Error finding merge commit for {branch}: {e}")

        # Fallback: return empty if we can't determine branch commits
        return []

    def _commits_to_info(self, commits: list[Any]) -> list[CommitInfo]:
        """Convert git commit objects to CommitInfo dataclasses."""
        result = []
        for c in commits:
            message = c.message
            if isinstance(message, bytes):
                message = message.decode("utf-8", errors="replace")
            result.append(
                CommitInfo(
                    hash=c.hexsha,
                    short_hash=c.hexsha[:7],
                    author_name=c.author.name or "",
                    author_email=c.author.email or "",
                    author_date=c.authored_datetime,
                    committer_name=c.committer.name or "",
                    committer_email=c.committer.email or "",
                    commit_date=c.committed_datetime,
                    message=message.strip(),
                    parent_hashes=[p.hexsha for p in c.parents],
                )
            )
        return result

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
        repo = self._get_repo(repo_path)
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

    def list_branches(self, repo_path: Path) -> list[str]:
        """
        List all branches in the repository.

        Returns both local and remote tracking branches, with the default
        branch first, followed by other branches ordered by last commit date
        (most recently modified first).

        Args:
            repo_path: Path to the git repository

        Returns:
            List of branch names sorted with default branch first,
            then by last commit date descending
        """
        repo = self._get_repo(repo_path)

        # Collect branches with their last commit dates
        branch_dates: dict[str, int] = {}

        # Get local branches with commit dates
        for ref in repo.heads:
            try:
                branch_dates[ref.name] = ref.commit.committed_date
            except (ValueError, GitCommandError):
                # Detached or broken ref — use epoch as fallback
                branch_dates[ref.name] = 0

        # Get remote tracking branches (strip remote prefix like "origin/")
        for ref in repo.remotes.origin.refs if repo.remotes else []:
            name = ref.remote_head
            if name and name != "HEAD" and name not in branch_dates:
                try:
                    branch_dates[name] = ref.commit.committed_date
                except (ValueError, GitCommandError):
                    # Detached or broken ref — use epoch as fallback
                    branch_dates[name] = 0

        branch_list = list(branch_dates.keys())
        default_branch = None

        # Determine default branch (prefer main, then master)
        for default_name in ["main", "master"]:
            if default_name in branch_list:
                default_branch = default_name
                break

        # If no default found, try to get from remote HEAD
        if default_branch is None and repo.remotes:
            try:
                head_ref = repo.remotes.origin.refs["HEAD"]
                # HEAD.reference points to the default branch
                default_branch = head_ref.reference.remote_head
            except (KeyError, AttributeError) as e:
                logger.debug(
                    "Could not determine default branch from remote HEAD for %s: %s",
                    repo_path,
                    e,
                )

        # Sort: default branch first, then by last commit date descending
        sorted_branches = sorted(
            branch_list,
            key=lambda b: (
                b != default_branch,  # Default branch first
                -branch_dates.get(b, 0),  # Then by date descending
            ),
        )

        return sorted_branches

    def get_tags(self, repo_path: Path) -> dict[str, list[str]]:
        """Return mapping of commit_hash -> [tag_names].

        Raises:
            GitOperationError: If the git operation fails.
        """
        repo = self._get_repo(repo_path)
        try:
            result: dict[str, list[str]] = {}
            for tag in repo.tags:
                commit_hash = tag.commit.hexsha
                result.setdefault(commit_hash, []).append(tag.name)
            return result
        except GitCommandError as e:
            raise GitOperationError("get_tags", str(e)) from e

    def get_blame(
        self,
        repo_path: Path,
        commit_hash: str,
        file_path: str,
    ) -> list[BlameLineInfo]:
        """Get blame information for each line of a file at a specific commit."""
        from datetime import UTC, datetime

        repo = self._get_repo(repo_path)
        try:
            commit = repo.commit(commit_hash)
        except (BadName, ValueError) as e:
            raise CommitNotFound(commit_hash=commit_hash) from e
        except GitCommandError as e:
            raise GitOperationError("get_blame", str(e)) from e

        try:
            blame_entries: Any = repo.blame(commit, file_path)
        except GitCommandError as e:
            raise FileNotFoundError(
                f"File not found at commit {commit_hash[:8]}"
            ) from e

        result: list[BlameLineInfo] = []
        line_number = 1
        for entry in blame_entries:
            blame_commit = entry[0]
            lines = entry[1]
            author_name = str(blame_commit.author.name or "")
            committed_date = datetime.fromtimestamp(blame_commit.committed_date, tz=UTC)
            short_hash: str = blame_commit.hexsha[:7]
            raw_message = blame_commit.message
            message = (
                raw_message.decode("utf-8", errors="replace")
                if isinstance(raw_message, bytes)
                else str(raw_message or "")
            ).strip()
            for _ in lines:
                result.append(
                    BlameLineInfo(
                        line_number=line_number,
                        commit_hash=blame_commit.hexsha,
                        short_hash=short_hash,
                        author_name=author_name,
                        commit_date=committed_date,
                        message=message,
                    )
                )
                line_number += 1

        return result

    def get_file_renames_in_commit(
        self,
        repo_path: Path,
        commit_hash: str,
    ) -> list[RenameInfo]:
        """Get file renames detected in a single commit (vs its parent).

        Uses GitPython's diff with rename detection to identify renames.
        """
        repo = self._get_repo(repo_path)
        try:
            commit = repo.commit(commit_hash)
        except (BadName, ValueError) as e:
            raise CommitNotFound(commit_hash=commit_hash) from e
        except GitCommandError as e:
            raise GitOperationError("get_file_renames_in_commit", str(e)) from e

        if not commit.parents:
            return []

        parent = commit.parents[0]
        try:
            diff = parent.diff(commit)
        except GitCommandError as e:
            raise GitOperationError("get_file_renames_in_commit", str(e)) from e

        renames: list[RenameInfo] = []
        for d in diff:
            if d.renamed_file and d.a_path and d.b_path:
                # GitPython stores similarity as a float 0-100 on d.score
                # (or as rename_from/rename_to). d.score may be None.
                similarity = int(d.score) if d.score is not None else 100
                renames.append(
                    RenameInfo(
                        old_path=d.a_path,
                        new_path=d.b_path,
                        similarity=similarity,
                    )
                )

        return renames

    def get_changed_files_in_commit(
        self,
        repo_path: Path,
        commit_hash: str,
    ) -> ChangedFiles:
        """
        Get files changed in a single commit (vs its parent).

        Args:
            repo_path: Path to the git repository
            commit_hash: Commit hash

        Returns:
            ChangedFiles with added, modified, and deleted file paths

        Raises:
            CommitNotFound: If the commit hash cannot be resolved.
            GitOperationError: If the git operation fails.
        """
        repo = self._get_repo(repo_path)
        try:
            commit = repo.commit(commit_hash)
        except (BadName, ValueError) as e:
            raise CommitNotFound(commit_hash=commit_hash) from e
        except GitCommandError as e:
            raise GitOperationError("get_changed_files_in_commit", str(e)) from e

        added: list[str] = []
        modified: list[str] = []
        deleted: list[str] = []

        if not commit.parents:
            # Initial commit - all files are "added"
            added = self.list_files(repo_path, commit_hash)
            return ChangedFiles(added=added, modified=modified, deleted=deleted)

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
                path = d.b_path or d.a_path
                if path:
                    modified.append(path)

        return ChangedFiles(added=added, modified=modified, deleted=deleted)

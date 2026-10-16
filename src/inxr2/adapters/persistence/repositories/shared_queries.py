"""Shared subquery builders for repository adapters.

Centralises the "branch head", "latest files" and "HEAD file IDs" logic used
by symbol_adapter, reference_adapter, file_search_adapter, dependency_adapter,
commit_adapter and postgres_text_search.

Every indexed commit is a full snapshot: commit_files links every file version
in that commit's tree. The files that exist on a branch are therefore exactly
the files linked to the branch's head commit (issue #547).

The head commit of a branch is the commit recorded as its last indexed commit
in index_status (the commit git reported as the branch HEAD). Only when no
index_status row matches does it fall back to the newest commit by
commit_date, then id. Ordering by date alone is unreliable: commits that share
a timestamp (rebases, cherry-picks, scripted commits) are common, and indexing
runs newest-first, so ids don't order them either (issue #549).
"""

from sqlalchemy import Subquery, case, func, select

from ..models.branch_commit import BranchCommitModel
from ..models.commit import CommitModel
from ..models.commit_file import CommitFileModel
from ..models.index_status import IndexStatusModel
from ..models.repository import RepositoryModel

# ---------------------------------------------------------------------------
# Raw SQL version of latest_file_ids_subquery(repo_id, branch) (used by
# reference resolution for performance in raw-SQL temp-table creation).
# Must stay equivalent to branch_head_commits_subquery + latest_file_ids_subquery.
# Bind parameters: :repo_id, :branch (NULL = the repository's default branch)
# ---------------------------------------------------------------------------
LATEST_FILE_IDS_SQL = """
    SELECT cf.file_id
    FROM commit_files cf
    WHERE cf.commit_id IN (
        SELECT ranked.commit_id FROM (
            SELECT c.id AS commit_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY bc.repository_id, bc.branch
                       ORDER BY
                           CASE WHEN c.commit_hash = s.last_indexed_commit
                                THEN 0 ELSE 1 END,
                           c.commit_date DESC,
                           c.id DESC
                   ) AS rn
            FROM branch_commits bc
            JOIN commits c ON c.id = bc.commit_id
            JOIN repositories r ON r.id = bc.repository_id
            LEFT JOIN index_status s
                ON s.repository_id = bc.repository_id AND s.branch = bc.branch
            WHERE bc.repository_id = :repo_id
              AND bc.branch = COALESCE(CAST(:branch AS VARCHAR), r.default_branch)
        ) ranked
        WHERE ranked.rn = 1
    )
"""


def branch_head_commits_subquery(
    repository_id: int | None = None,
    branch: str | None = None,
) -> Subquery:
    """Subquery returning the head commit of each selected (repository, branch).

    The head is the branch's last indexed commit from index_status, falling
    back to the newest commit by commit_date, then id, when index_status has
    no matching row (see module docstring).

    When branch is provided, selects that branch. When branch is None,
    selects each repository's default branch. When repository_id is None,
    covers all repositories.

    Columns: ``repository_id``, ``commit_id``.
    """
    is_not_indexed_head = case(
        (CommitModel.commit_hash == IndexStatusModel.last_indexed_commit, 0),
        else_=1,
    )
    ranked_query = (
        select(
            BranchCommitModel.repository_id.label("repository_id"),
            CommitModel.id.label("commit_id"),
            func.row_number()
            .over(
                partition_by=[
                    BranchCommitModel.repository_id,
                    BranchCommitModel.branch,
                ],
                order_by=[
                    is_not_indexed_head,
                    CommitModel.commit_date.desc(),
                    CommitModel.id.desc(),
                ],
            )
            .label("rn"),
        )
        .join(CommitModel, CommitModel.id == BranchCommitModel.commit_id)
        .outerjoin(
            IndexStatusModel,
            (IndexStatusModel.repository_id == BranchCommitModel.repository_id)
            & (IndexStatusModel.branch == BranchCommitModel.branch),
        )
    )
    if repository_id is not None:
        ranked_query = ranked_query.where(
            BranchCommitModel.repository_id == repository_id
        )
    if branch is not None:
        ranked_query = ranked_query.where(BranchCommitModel.branch == branch)
    else:
        ranked_query = ranked_query.join(
            RepositoryModel,
            (RepositoryModel.id == BranchCommitModel.repository_id)
            & (BranchCommitModel.branch == RepositoryModel.default_branch),
        )
    ranked = ranked_query.subquery()
    return (
        select(ranked.c.repository_id, ranked.c.commit_id)
        .where(ranked.c.rn == 1)
        .subquery()
    )


def latest_file_ids_subquery(
    repository_id: int | None = None,
    branch: str | None = None,
) -> Subquery:
    """Subquery returning the file IDs present at the branch head.

    Paths deleted before the head have no commit_files row there and are
    excluded. Ranking file versions per path across *all* commits instead
    would resurrect a deleted path from the last commit that still
    contained it (issue #547).

    When branch is provided, returns the files at that branch's head.
    When branch is None, returns the files at the head of the repository's
    default branch — the same scope browse, symbol search and code search
    use when no branch is given.

    When repository_id is None, covers all repositories.

    The output column is named ``max_id`` for compatibility with callers.
    """
    heads = branch_head_commits_subquery(repository_id, branch)
    return (
        select(CommitFileModel.file_id.label("max_id"))
        .where(CommitFileModel.commit_id.in_(select(heads.c.commit_id)))
        .subquery()
    )


def head_file_ids_subquery() -> Subquery:
    """File IDs at HEAD of each repo's default branch (for global search)."""
    heads = branch_head_commits_subquery()
    return (
        select(CommitFileModel.file_id.label("file_id"))
        .where(CommitFileModel.commit_id.in_(select(heads.c.commit_id)))
        .subquery()
    )

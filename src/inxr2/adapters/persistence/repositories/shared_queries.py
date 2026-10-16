"""Shared subquery builders for repository adapters.

Centralises the "latest file per path" and "HEAD file IDs" logic that was
previously duplicated across symbol_adapter, reference_adapter, file_adapter,
and postgres_text_search.
"""

from sqlalchemy import Subquery, func, select

from ..models.branch_commit import BranchCommitModel
from ..models.commit import CommitModel
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel
from ..models.repository import RepositoryModel

# ---------------------------------------------------------------------------
# Raw SQL version of latest_file_ids_subquery(repo_id) (used by
# resolve_references_batch for performance in raw-SQL temp-table creation).
# Bind parameter: :repo_id
# ---------------------------------------------------------------------------
LATEST_FILE_IDS_SQL = """
    SELECT sub.file_id FROM (
        SELECT f.id AS file_id,
               ROW_NUMBER() OVER (
                   PARTITION BY f.repository_id, f.path
                   ORDER BY heads.commit_date DESC, heads.commit_id DESC
               ) AS rn
        FROM files f
        JOIN commit_files cf ON cf.file_id = f.id
        JOIN (
            SELECT ranked.commit_id, ranked.commit_date FROM (
                SELECT c.id AS commit_id,
                       c.commit_date,
                       ROW_NUMBER() OVER (
                           PARTITION BY bc.repository_id, bc.branch
                           ORDER BY c.commit_date DESC, c.id DESC
                       ) AS rn
                FROM branch_commits bc
                JOIN commits c ON c.id = bc.commit_id
                WHERE bc.repository_id = :repo_id
            ) ranked
            WHERE ranked.rn = 1
        ) heads ON heads.commit_id = cf.commit_id
        WHERE f.repository_id = :repo_id
    ) sub
    WHERE sub.rn = 1
"""


def branch_head_commits_subquery(
    repository_id: int | None = None,
    branch: str | None = None,
) -> Subquery:
    """Subquery returning the head commit of each indexed branch.

    The head is the newest commit (by commit_date, then id) linked to the
    branch via branch_commits. Columns: ``commit_id``, ``commit_date``.

    Optionally restricted to one repository and/or one branch name.
    """
    ranked_query = select(
        CommitModel.id.label("commit_id"),
        CommitModel.commit_date.label("commit_date"),
        func.row_number()
        .over(
            partition_by=[BranchCommitModel.repository_id, BranchCommitModel.branch],
            order_by=[CommitModel.commit_date.desc(), CommitModel.id.desc()],
        )
        .label("rn"),
    ).join(CommitModel, CommitModel.id == BranchCommitModel.commit_id)
    if repository_id is not None:
        ranked_query = ranked_query.where(
            BranchCommitModel.repository_id == repository_id
        )
    if branch is not None:
        ranked_query = ranked_query.where(BranchCommitModel.branch == branch)
    ranked = ranked_query.subquery()
    return (
        select(ranked.c.commit_id, ranked.c.commit_date)
        .where(ranked.c.rn == 1)
        .subquery()
    )


def latest_file_ids_subquery(
    repository_id: int | None = None,
    branch: str | None = None,
) -> Subquery:
    """Subquery returning the file IDs present at the branch head(s).

    Every indexed commit is a full snapshot (commit_files links every file
    version in its tree), so the files at a branch's head commit are exactly
    the files that exist on that branch. Paths deleted before the head have
    no row there and are excluded (issue #547). Ranking file versions per
    path across *all* commits instead would resurrect a deleted path from the
    last commit that still contained it.

    When branch is provided, returns the files at that branch's head.
    When branch is None, returns the files at the head of every indexed
    branch, deduplicated per (repository_id, path) by the newest head, so a
    path that still exists on any branch head is included once.

    When repository_id is None, covers all repositories.

    The output column is named ``max_id`` for compatibility with callers.
    """
    heads = branch_head_commits_subquery(repository_id, branch)
    inner_query = (
        select(
            FileModel.id.label("file_id"),
            func.row_number()
            .over(
                partition_by=[FileModel.repository_id, FileModel.path],
                order_by=[heads.c.commit_date.desc(), heads.c.commit_id.desc()],
            )
            .label("rn"),
        )
        .join(CommitFileModel, CommitFileModel.file_id == FileModel.id)
        .join(heads, heads.c.commit_id == CommitFileModel.commit_id)
    )
    if repository_id is not None:
        inner_query = inner_query.where(FileModel.repository_id == repository_id)
    inner = inner_query.subquery()
    return select(inner.c.file_id.label("max_id")).where(inner.c.rn == 1).subquery()


def head_file_ids_subquery() -> Subquery:
    """File IDs at HEAD of each repo's default branch (for global search).

    Finds the latest commit on each repository's default branch, then
    returns all file IDs linked to those HEAD commits via commit_files.
    """
    inner = (
        select(
            RepositoryModel.id.label("repo_id"),
            BranchCommitModel.commit_id.label("commit_id"),
            func.row_number()
            .over(
                partition_by=RepositoryModel.id,
                order_by=[CommitModel.commit_date.desc(), CommitModel.id.desc()],
            )
            .label("rn"),
        )
        .join(
            BranchCommitModel,
            (BranchCommitModel.repository_id == RepositoryModel.id)
            & (BranchCommitModel.branch == RepositoryModel.default_branch),
        )
        .join(CommitModel, CommitModel.id == BranchCommitModel.commit_id)
        .subquery()
    )
    head_commits = select(inner.c.commit_id).where(inner.c.rn == 1).subquery()

    return (
        select(CommitFileModel.file_id.label("file_id"))
        .where(CommitFileModel.commit_id.in_(select(head_commits.c.commit_id)))
        .subquery()
    )

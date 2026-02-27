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

# ---------------------------------------------------------------------------
# Raw SQL version of latest_file_ids_subquery (used by resolve_references_batch
# for performance in raw-SQL temp-table creation).
# Bind parameter: :repo_id
# ---------------------------------------------------------------------------
LATEST_FILE_IDS_SQL = """
    SELECT sub.file_id FROM (
        SELECT f.id AS file_id,
               ROW_NUMBER() OVER (
                   PARTITION BY f.repository_id, f.path
                   ORDER BY c.commit_date DESC, c.id DESC
               ) AS rn
        FROM files f
        JOIN commit_files cf ON cf.file_id = f.id
        JOIN commits c ON c.id = cf.commit_id
        WHERE f.repository_id = :repo_id
    ) sub
    WHERE sub.rn = 1
"""


def latest_file_ids_subquery(
    repository_id: int | None = None,
    branch: str | None = None,
) -> Subquery:
    """Subquery returning the latest file ID per (repository_id, path).

    Uses commit dates via commit_files junction to determine "latest",
    which is correct even for HEAD-first indexing where newer commits
    may have lower file IDs.

    When repository_id is None, returns the latest files across all
    repositories. When provided, filters to that specific repository.

    When branch is provided, only considers files from commits on that
    branch, so "latest" is scoped to the branch rather than global.
    If repository_id is None but branch is provided, filters to commits
    on branches with that name across all repositories.
    """
    inner_query = (
        select(
            FileModel.id.label("file_id"),
            func.row_number()
            .over(
                partition_by=[FileModel.repository_id, FileModel.path],
                order_by=[
                    CommitModel.commit_date.desc(),
                    CommitModel.id.desc(),
                ],
            )
            .label("rn"),
        )
        .join(CommitFileModel, CommitFileModel.file_id == FileModel.id)
        .join(CommitModel, CommitModel.id == CommitFileModel.commit_id)
    )
    if repository_id is not None:
        inner_query = inner_query.where(FileModel.repository_id == repository_id)
    if branch is not None:
        join_cond = BranchCommitModel.commit_id == CommitFileModel.commit_id
        if repository_id is not None:
            join_cond = join_cond & (BranchCommitModel.repository_id == repository_id)
        inner_query = inner_query.join(
            BranchCommitModel,
            join_cond & (BranchCommitModel.branch == branch),
        )
    inner = inner_query.subquery()
    return select(inner.c.file_id.label("max_id")).where(inner.c.rn == 1).subquery()

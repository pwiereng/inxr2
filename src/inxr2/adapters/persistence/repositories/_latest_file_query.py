"""Reusable subquery for finding the latest file ID per path.

The indexer processes commits HEAD-first (newest first), so HEAD files get
lower auto-increment IDs. Using max(id) to find "latest" actually returns
the oldest commit's file. This module provides the correct approach: ordering
by commit_date desc via ROW_NUMBER().
"""

from sqlalchemy import Select, func, select

from ..models.branch_commit import BranchCommitModel
from ..models.commit import CommitModel
from ..models.file import FileModel


def latest_file_ids_subquery(
    repository_id: int, branch: str | None = None
) -> Select[tuple[int]]:
    """Build a subquery returning the latest file ID per path.

    Uses ROW_NUMBER() partitioned by path, ordered by commit_date desc
    (with commit.id desc as tiebreaker), then filters to rn=1.

    Args:
        repository_id: The repository to query.
        branch: Optional branch name. When provided, only considers files
                from commits on this branch.

    Returns:
        A Select yielding rows with a single ``latest_id`` column.
    """
    ranked = (
        select(
            FileModel.id.label("file_id"),
            func.row_number()
            .over(
                partition_by=FileModel.path,
                order_by=(CommitModel.commit_date.desc(), CommitModel.id.desc()),
            )
            .label("rn"),
        )
        .join(CommitModel, FileModel.commit_id == CommitModel.id)
        .where(FileModel.repository_id == repository_id)
    )

    if branch is not None:
        ranked = ranked.join(
            BranchCommitModel, BranchCommitModel.commit_id == CommitModel.id
        ).where(
            BranchCommitModel.branch == branch,
            BranchCommitModel.repository_id == repository_id,
        )

    ranked_sq = ranked.subquery()

    return select(ranked_sq.c.file_id.label("latest_id")).where(ranked_sq.c.rn == 1)

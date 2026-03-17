"""QueryLog ORM model."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class QueryLogModel(Base):
    """SQLAlchemy ORM model for query_log table (ring-buffer activity log)."""

    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now(), index=True
    )
    source: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    tool_or_path: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    repository: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    status_code: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<QueryLogModel(id={self.id}, source='{self.source}', "
            f"tool_or_path='{self.tool_or_path}', logged_at={self.logged_at})>"
        )

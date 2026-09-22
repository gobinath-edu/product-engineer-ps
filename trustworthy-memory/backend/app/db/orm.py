from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.domain.states import MemoryState


class MemoryORM(Base):
    """
    SQLAlchemy persistence model for a memory.

    Historical records are retained. Corrections and deletions change
    lifecycle state rather than physically removing the row.
    """

    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    predicate: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    object_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    normalized_subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    normalized_predicate: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    normalized_object: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    state: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=MemoryState.ACTIVE.value,
        index=True,
    )

    supersedes_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    superseded_by_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_memories_logical_lookup",
            "normalized_subject",
            "normalized_predicate",
        ),
        Index(
            "ix_memories_active_lookup",
            "normalized_subject",
            "normalized_predicate",
            "state",
        ),
    )
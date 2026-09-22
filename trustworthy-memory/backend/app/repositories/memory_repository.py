from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.orm import MemoryORM
from app.domain.models import Memory
from app.domain.states import MemoryState


class MemoryRepository:
    """
    Persistence boundary for memory records.

    Business decisions such as whether something should supersede another
    memory belong in the service/domain layer, not here.
    """

    def __init__(self, db: Session):
        self.db = db

    def add(self, memory: Memory) -> Memory:
        record = self._to_orm(memory)

        self.db.add(record)
        self.db.flush()

        return memory

    def get_by_id(self, memory_id: str) -> Optional[Memory]:
        record = self.db.get(MemoryORM, memory_id)

        if record is None:
            return None

        return self._to_domain(record)

    def list_all(self) -> list[Memory]:
        statement = (
            select(MemoryORM)
            .order_by(
                MemoryORM.created_at.asc(),
                MemoryORM.id.asc(),
            )
        )

        records = self.db.scalars(statement).all()

        return [self._to_domain(record) for record in records]

    def list_active(self) -> list[Memory]:
        statement = (
            select(MemoryORM)
            .where(
                MemoryORM.state == MemoryState.ACTIVE.value
            )
            .order_by(
                MemoryORM.created_at.asc(),
                MemoryORM.id.asc(),
            )
        )

        records = self.db.scalars(statement).all()

        return [self._to_domain(record) for record in records]

    def list_by_logical_key(
        self,
        normalized_subject: str,
        normalized_predicate: str,
    ) -> list[Memory]:
        statement = (
            select(MemoryORM)
            .where(
                MemoryORM.normalized_subject == normalized_subject,
                MemoryORM.normalized_predicate == normalized_predicate,
            )
            .order_by(
                MemoryORM.created_at.asc(),
                MemoryORM.id.asc(),
            )
        )

        records = self.db.scalars(statement).all()

        return [self._to_domain(record) for record in records]

    def list_by_source(self, source_id: str) -> list[Memory]:
        statement = (
            select(MemoryORM)
            .where(MemoryORM.source_id == source_id)
            .order_by(
                MemoryORM.created_at.asc(),
                MemoryORM.id.asc(),
            )
        )

        records = self.db.scalars(statement).all()

        return [self._to_domain(record) for record in records]

    def update_state(
        self,
        memory_id: str,
        state: MemoryState,
        updated_at: datetime,
        *,
        superseded_by_id: Optional[str] = None,
        deleted_at: Optional[datetime] = None,
    ) -> Optional[Memory]:
        record = self.db.get(MemoryORM, memory_id)

        if record is None:
            return None

        record.state = state.value
        record.updated_at = updated_at
        record.superseded_by_id = superseded_by_id
        record.deleted_at = deleted_at

        self.db.flush()

        return self._to_domain(record)

    def set_supersedes_id(
        self,
        memory_id: str,
        supersedes_id: str,
        updated_at: datetime,
    ) -> Optional[Memory]:
        record = self.db.get(MemoryORM, memory_id)

        if record is None:
            return None

        record.supersedes_id = supersedes_id
        record.updated_at = updated_at

        self.db.flush()

        return self._to_domain(record)

    @staticmethod
    def _to_orm(memory: Memory) -> MemoryORM:
        return MemoryORM(
            id=memory.id,
            subject=memory.subject,
            predicate=memory.predicate,
            object_value=memory.object_value,
            content=memory.content,
            normalized_subject=memory.subject,
            normalized_predicate=memory.predicate,
            normalized_object=memory.object_value,
            source_id=memory.source_id,
            source_type=memory.source_type,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            state=memory.state.value,
            supersedes_id=memory.supersedes_id,
            superseded_by_id=memory.superseded_by_id,
            deleted_at=memory.deleted_at,
        )

    @staticmethod
    def _to_domain(record: MemoryORM) -> Memory:
        return Memory(
            id=record.id,
            subject=record.subject,
            predicate=record.predicate,
            object_value=record.object_value,
            content=record.content,
            source_id=record.source_id,
            source_type=record.source_type,
            created_at=record.created_at,
            updated_at=record.updated_at,
            state=MemoryState(record.state),
            supersedes_id=record.supersedes_id,
            superseded_by_id=record.superseded_by_id,
            deleted_at=record.deleted_at,
        )
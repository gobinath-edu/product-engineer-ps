from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.determinism import stable_id, utc_now
from app.domain.errors import (
    InvalidMemoryError,
    InvalidStateTransitionError,
    MemoryNotFoundError,
)
from app.domain.models import Memory
from app.domain.rules import (
    normalize_memory_fields,
    validate_state_transition,
)
from app.domain.states import MemoryState
from app.repositories.memory_repository import MemoryRepository
from app.services.provenance_service import ProvenanceService
from app.services.reconciliation_service import (
    ReconciliationService,
)


class MemoryService:
    """
    Application service responsible for memory lifecycle operations.
    """

    def __init__(self, db: Session):
        self.repository = MemoryRepository(db)
        self.provenance = ProvenanceService()
        self.reconciliation = ReconciliationService()

    def create_memory(
        self,
        *,
        subject: str,
        predicate: str,
        object_value: str,
        content: str,
        source_id: str,
        source_type: str = "message",
        created_at: Optional[datetime] = None,
    ) -> Memory:
        if not subject.strip():
            raise InvalidMemoryError("subject must not be empty")

        if not predicate.strip():
            raise InvalidMemoryError("predicate must not be empty")

        if not object_value.strip():
            raise InvalidMemoryError(
                "object_value must not be empty"
            )

        if not content.strip():
            raise InvalidMemoryError("content must not be empty")

        normalized_subject, normalized_predicate, normalized_object = (
            normalize_memory_fields(
                subject,
                predicate,
                object_value,
            )
        )

        provenance = self.provenance.create(
            source_id=source_id,
            source_type=source_type,
        )

        timestamp = created_at or utc_now()

        memory_id = stable_id(
            provenance.source_type,
            provenance.source_id,
            normalized_subject,
            normalized_predicate,
            normalized_object,
        )

        existing_memories = self.repository.list_by_logical_key(
            normalized_subject,
            normalized_predicate,
        )

        active_memory = next(
            (
                memory
                for memory in existing_memories
                if memory.state == MemoryState.ACTIVE
            ),
            None,
        )

        decision = self.reconciliation.decide(
            candidate_subject=normalized_subject,
            candidate_predicate=normalized_predicate,
            candidate_content=content,
            existing_memory=active_memory,
        )

        if decision.action == "preserve_existing":
            if active_memory is None:
                raise InvalidMemoryError(
                    "Reconciliation returned preserve_existing "
                    "without an active memory."
                )

            return active_memory

        memory = Memory(
            id=memory_id,
            subject=normalized_subject,
            predicate=normalized_predicate,
            object_value=normalized_object,
            content=content.strip(),
            source_id=provenance.source_id,
            source_type=provenance.source_type,
            created_at=timestamp,
            updated_at=timestamp,
            state=MemoryState.ACTIVE,
            supersedes_id=(
                active_memory.id
                if decision.action == "supersede"
                and active_memory is not None
                else None
            ),
        )

        if decision.action == "supersede" and active_memory is not None:
            self._supersede_existing(
                active_memory,
                timestamp,
                memory.id,
            )

        self.repository.add(memory)

        return memory

    def get_memory(self, memory_id: str) -> Memory:
        memory = self.repository.get_by_id(memory_id)

        if memory is None:
            raise MemoryNotFoundError(
                f"Memory not found: {memory_id}"
            )

        return memory

    def delete_memory(
        self,
        memory_id: str,
        deleted_at: Optional[datetime] = None,
    ) -> Memory:
        memory = self.get_memory(memory_id)

        if not validate_state_transition(
            memory.state,
            MemoryState.DELETED,
        ):
            raise InvalidStateTransitionError(
                f"Cannot delete memory in state {memory.state.value}"
            )

        timestamp = deleted_at or utc_now()

        deleted = self.repository.update_state(
            memory_id,
            MemoryState.DELETED,
            timestamp,
            deleted_at=timestamp,
        )

        if deleted is None:
            raise MemoryNotFoundError(
                f"Memory not found: {memory_id}"
            )

        return deleted

    def list_all(self) -> list[Memory]:
        return self.repository.list_all()

    def list_active(self) -> list[Memory]:
        return self.repository.list_active()

    def _supersede_existing(
        self,
        existing: Memory,
        timestamp: datetime,
        superseded_by_id: str,
    ) -> None:
        if not validate_state_transition(
            existing.state,
            MemoryState.SUPERSEDED,
        ):
            raise InvalidStateTransitionError(
                f"Cannot supersede memory in state "
                f"{existing.state.value}"
            )

        updated = self.repository.update_state(
            existing.id,
            MemoryState.SUPERSEDED,
            timestamp,
            superseded_by_id=superseded_by_id,
        )

        if updated is None:
            raise MemoryNotFoundError(
                f"Memory not found: {existing.id}"
            )
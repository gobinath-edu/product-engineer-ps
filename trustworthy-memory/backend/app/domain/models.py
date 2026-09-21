from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .states import MemoryState


@dataclass(frozen=True)
class Memory:
    """
    Domain representation of a single stored memory.

    A memory is immutable at the domain level. Corrections create a new
    memory and supersede the previous one instead of overwriting history.
    """

    id: str
    subject: str
    predicate: str
    object_value: str
    content: str

    source_id: str
    source_type: str

    created_at: datetime
    updated_at: datetime

    state: MemoryState = MemoryState.ACTIVE

    supersedes_id: Optional[str] = None
    superseded_by_id: Optional[str] = None
    deleted_at: Optional[datetime] = None

    def is_active(self) -> bool:
        return self.state == MemoryState.ACTIVE

    def is_superseded(self) -> bool:
        return self.state == MemoryState.SUPERSEDED

    def is_deleted(self) -> bool:
        return self.state == MemoryState.DELETED
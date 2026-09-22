from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.services.memory_service import MemoryService
from app.domain.states import MemoryState


def create_test_session():
    """
    Create a completely isolated in-memory SQLite database
    for each test.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(bind=engine)

    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    return session_factory()


def test_first_memory_is_active():
    """
    Test that a brand-new memory is stored as ACTIVE.
    """

    db = create_test_session()
    service = MemoryService(db)

    memory = service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Pune",
        content="I live in Pune.",
        source_id="msg-001",
    )

    db.commit()

    assert memory.state == MemoryState.ACTIVE
    assert memory.object_value == "pune"
    assert memory.supersedes_id is None


def test_explicit_correction_supersedes_old_memory():
    """
    Test the main correction scenario:

    Pune -> Mumbai

    The old Pune memory becomes SUPERSEDED.
    The new Mumbai memory becomes ACTIVE.
    """

    db = create_test_session()
    service = MemoryService(db)

    first = service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Pune",
        content="I live in Pune.",
        source_id="msg-001",
    )

    db.commit()

    second = service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Mumbai",
        content="Actually, I moved to Mumbai.",
        source_id="msg-002",
    )

    db.commit()

    old = service.get_memory(first.id)
    current = service.get_memory(second.id)

    assert old.state == MemoryState.SUPERSEDED
    assert old.superseded_by_id == second.id

    assert current.state == MemoryState.ACTIVE
    assert current.supersedes_id == first.id
    assert current.object_value == "mumbai"


def test_old_memory_remains_in_history():
    """
    Supersession must NOT physically delete the old memory.

    Both Pune and Mumbai should still exist in historical storage.
    """

    db = create_test_session()
    service = MemoryService(db)

    first = service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Pune",
        content="I live in Pune.",
        source_id="msg-001",
    )

    db.commit()

    second = service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Mumbai",
        content="Actually, I moved to Mumbai.",
        source_id="msg-002",
    )

    db.commit()

    all_memories = service.list_all()

    ids = {memory.id for memory in all_memories}

    assert first.id in ids
    assert second.id in ids
    assert len(all_memories) == 2


def test_ambiguous_statement_does_not_replace_current_memory():
    """
    An uncertain statement should NOT automatically replace
    the existing residence.

    Example:

    Existing:
        I live in Pune.

    New:
        I might be staying in Chennai this week.

    Pune should remain ACTIVE.
    """

    db = create_test_session()
    service = MemoryService(db)

    first = service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Pune",
        content="I live in Pune.",
        source_id="msg-001",
    )

    db.commit()

    candidate = service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Chennai",
        content="I might be staying in Chennai this week.",
        source_id="msg-002",
    )

    db.commit()

    # Because the new statement is ambiguous,
    # the service should preserve the existing memory.
    assert candidate.id == first.id

    current = service.get_memory(first.id)

    assert current.state == MemoryState.ACTIVE
    assert current.object_value == "pune"

    # No second memory should have been created.
    assert len(service.list_all()) == 1


def test_delete_removes_memory_from_active_results():
    """
    Deleted memories must disappear from active retrieval
    while remaining available in historical storage.
    """

    db = create_test_session()
    service = MemoryService(db)

    memory = service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Pune",
        content="I live in Pune.",
        source_id="msg-001",
    )

    db.commit()

    deleted = service.delete_memory(
        memory.id,
        deleted_at=datetime.now(timezone.utc),
    )

    db.commit()

    assert deleted.state == MemoryState.DELETED

    # Deleted memory must not appear in active memories.
    assert service.list_active() == []

    # But history must still contain it.
    history = service.list_all()

    assert len(history) == 1
    assert history[0].state == MemoryState.DELETED
    def test_memory_preserves_source_provenance():"""
    Stored memories must retain the provenance information
    needed to trace them back to their originating source.
    """

    db = create_test_session()
    service = MemoryService(db)

    memory = service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Pune",
        content="I live in Pune.",
        source_id="msg-001",
    )

    db.commit()

    stored = service.get_memory(memory.id)

    assert stored.source_id == "msg-001"
    assert stored.source_type == "message"
    assert stored.created_at is not None
    assert stored.updated_at is not None
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.domain.states import MemoryState
from app.repositories.memory_repository import MemoryRepository
from app.services.memory_service import MemoryService
from app.services.retrieval_service import RetrievalService


def create_test_session():
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


def create_retrieval_service():
    db = create_test_session()

    memory_service = MemoryService(db)

    repository = MemoryRepository(db)

    retrieval_service = RetrievalService(repository)

    return db, memory_service, retrieval_service


def test_retrieval_returns_relevant_active_memory():
    db, memory_service, retrieval_service = (
        create_retrieval_service()
    )

    memory_service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Mumbai",
        content="I live in Mumbai.",
        source_id="msg-001",
    )

    memory_service.create_memory(
        subject="user_1",
        predicate="favorite_color",
        object_value="Blue",
        content="My favorite color is blue.",
        source_id="msg-002",
    )

    db.commit()

    results = retrieval_service.retrieve(
        "Where do I live?",
        subject="user_1",
        predicate="residence",
    )

    assert results

    assert results[0].memory.object_value == "mumbai"
    assert results[0].memory.state == MemoryState.ACTIVE


def test_superseded_memory_is_excluded():
    db, memory_service, retrieval_service = (
        create_retrieval_service()
    )

    old_memory = memory_service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Pune",
        content="I live in Pune.",
        source_id="msg-001",
    )

    db.commit()

    current_memory = memory_service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Mumbai",
        content="Actually, I moved to Mumbai.",
        source_id="msg-002",
    )

    db.commit()

    results = retrieval_service.retrieve(
        "Where do I live?",
        subject="user_1",
        predicate="residence",
    )

    result_ids = {
        result.memory.id
        for result in results
    }

    assert current_memory.id in result_ids
    assert old_memory.id not in result_ids


def test_deleted_memory_is_excluded():
    db, memory_service, retrieval_service = (
        create_retrieval_service()
    )

    memory = memory_service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Pune",
        content="I live in Pune.",
        source_id="msg-001",
    )

    db.commit()

    memory_service.delete_memory(memory.id)

    db.commit()

    results = retrieval_service.retrieve(
        "Where do I live?",
        subject="user_1",
        predicate="residence",
    )

    result_ids = {
        result.memory.id
        for result in results
    }

    assert memory.id not in result_ids


def test_retrieval_is_bounded():
    db, memory_service, retrieval_service = (
        create_retrieval_service()
    )

    for index in range(10):
        memory_service.create_memory(
            subject="user_1",
            predicate="skill",
            object_value=f"Skill {index}",
            content=f"I know skill {index}.",
            source_id=f"msg-{index:03d}",
        )

    db.commit()

    results = retrieval_service.retrieve(
        "skills",
        subject="user_1",
        predicate="skill",
        top_k=3,
    )

    assert len(results) <= 3


def test_retrieval_evidence_is_present():
    db, memory_service, retrieval_service = (
        create_retrieval_service()
    )

    memory_service.create_memory(
        subject="user_1",
        predicate="residence",
        object_value="Mumbai",
        content="I live in Mumbai.",
        source_id="msg-001",
    )

    db.commit()

    results = retrieval_service.retrieve(
        "Mumbai",
        subject="user_1",
        predicate="residence",
    )

    assert results

    evidence = results[0].evidence

    assert evidence.score > 0
    assert evidence.matched_fields
    assert evidence.evidence
    assert "structured=" in evidence.evidence
    assert "lexical=" in evidence.evidence


def test_retrieval_order_is_deterministic():
    db, memory_service, retrieval_service = (
        create_retrieval_service()
    )

    memory_service.create_memory(
        subject="user_1",
        predicate="skill",
        object_value="Python",
        content="I know Python.",
        source_id="msg-001",
    )

    memory_service.create_memory(
        subject="user_1",
        predicate="skill",
        object_value="Python Machine Learning",
        content="I know Python and machine learning.",
        source_id="msg-002",
    )

    db.commit()

    first_run = retrieval_service.retrieve(
        "Python",
        subject="user_1",
        predicate="skill",
    )

    second_run = retrieval_service.retrieve(
        "Python",
        subject="user_1",
        predicate="skill",
    )

    first_ids = [
        result.memory.id
        for result in first_run
    ]

    second_ids = [
        result.memory.id
        for result in second_run
    ]

    assert first_ids == second_ids
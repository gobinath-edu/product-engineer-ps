from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, initialize_database
from app.domain.errors import DomainError, MemoryNotFoundError
from app.services.memory_service import MemoryService
from app.services.retrieval_service import RetrievalService


app = FastAPI(title="Trustworthy Long-Term Memory API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    subject: str = "user-001"


class ChatResponse(BaseModel):
    reply: str
    action: str
    memory: dict[str, Any] | None = None
    memories: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []


class MemoryOut(BaseModel):
    id: str
    subject: str
    predicate: str
    object_value: str
    content: str
    source_id: str
    source_type: str
    created_at: str
    updated_at: str
    state: str
    supersedes_id: str | None = None
    superseded_by_id: str | None = None
    deleted_at: str | None = None


def serialize_memory(memory) -> dict[str, Any]:
    def iso(value):
        return value.isoformat() if value else None

    return {
        "id": memory.id,
        "subject": memory.subject,
        "predicate": memory.predicate,
        "object_value": memory.object_value,
        "content": memory.content,
        "source_id": memory.source_id,
        "source_type": memory.source_type,
        "created_at": iso(memory.created_at),
        "updated_at": iso(memory.updated_at),
        "state": memory.state.value,
        "supersedes_id": memory.supersedes_id,
        "superseded_by_id": memory.superseded_by_id,
        "deleted_at": iso(memory.deleted_at),
    }


def parse_statement(message: str) -> tuple[str, str, str] | None:
    text = message.strip()
    lower = text.lower().rstrip(".!?")

    patterns = [
        (r"^(?:actually,\s*)?i\s+(?:currently\s+)?live\s+in\s+(.+)$", "residence"),
        (r"^(?:actually,\s*)?i\s+moved\s+to\s+(.+)$", "city"),
        (r"^(?:actually,\s*)?i\s+(?:now\s+)?work\s+at\s+(.+)$", "employer"),
        (r"^(?:actually,\s*)?my\s+(?:current\s+)?(?:job\s+title|role)\s+is\s+(?:now\s+)?(.+)$", "job_title"),
        (r"^(?:actually,\s*)?my\s+(?:favorite\s+color)\s+is\s+(.+)$", "favorite_color"),
        (r"^(?:actually,\s*)?my\s+blood\s+group\s+is\s+(.+)$", "blood_group"),
        (r"^(?:actually,\s*)?my\s+(?:phone|mobile)\s+(?:number\s+)?is\s+(.+)$", "phone"),
        (r"^(?:actually,\s*)?i\s+(?:know|use|work\s+with)\s+(.+)$", "skill"),
        (r"^(?:actually,\s*)?i\s+(?:speak|can\s+speak)\s+(.+)$", "language"),
        (r"^(?:actually,\s*)?i\s+(?:like|love|am\s+interested\s+in)\s+(.+)$", "interest"),
    ]

    for pattern, predicate in patterns:
        match = re.match(pattern, lower, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip().rstrip(".!?")
            # Avoid treating uncertain statements as definite memories.
            if re.search(r"\b(might|maybe|possibly|not sure|i think|could be|probably)\b", lower):
                return None
            return "user-001", predicate, value

    return None


def is_question(message: str) -> bool:
    text = message.strip().lower()
    return (
        "?" in text
        or text.startswith(("where ", "what ", "which ", "who ", "do i ", "am i ", "what's ", "what is "))
    )


def make_answer(query: str, results: list[dict[str, Any]]) -> str:
    if not results:
        return "I couldn't find a relevant active memory for that."

    q = query.lower()

    if any(x in q for x in ("where do i live", "where am i", "where do i currently live")):
        candidates = [r for r in results if r["predicate"] in ("residence", "city")]
        if candidates:
            return f"You currently live in {candidates[0]['object_value'].title()}."

    if "work" in q or "employer" in q or "company" in q:
        candidates = [r for r in results if r["predicate"] == "employer"]
        if candidates:
            return f"You currently work at {candidates[0]['object_value'].title()}."

    if "job" in q or "role" in q or "title" in q:
        candidates = [r for r in results if r["predicate"] == "job_title"]
        if candidates:
            return f"Your current role is {candidates[0]['object_value'].title()}."

    if "favorite color" in q:
        candidates = [r for r in results if r["predicate"] == "favorite_color"]
        if candidates:
            return f"Your favorite color is {candidates[0]['object_value'].title()}."

    if "phone" in q or "mobile" in q:
        candidates = [r for r in results if r["predicate"] == "phone"]
        if candidates:
            return f"Your current phone number is {candidates[0]['object_value']}."

    if "blood" in q:
        candidates = [r for r in results if r["predicate"] == "blood_group"]
        if candidates:
            return f"Your stored blood group is {candidates[0]['object_value'].upper()}."

    if "language" in q or "speak" in q:
        candidates = [r for r in results if r["predicate"] == "language"]
        if candidates:
            values = ", ".join(sorted({r["object_value"].title() for r in candidates}))
            return f"You have stored language memories for {values}."

    if "skill" in q or "programming" in q or "know" in q:
        candidates = [r for r in results if r["predicate"] == "skill"]
        if candidates:
            values = ", ".join(sorted({r["object_value"].title() for r in candidates}))
            return f"You have stored skills including {values}."

    if "interest" in q or "interested" in q:
        candidates = [r for r in results if r["predicate"] == "interest"]
        if candidates:
            values = ", ".join(sorted({r["object_value"].title() for r in candidates}))
            return f"You have stored interests including {values}."

    top = results[0]
    return f"I found an active memory: {top['predicate'].replace('_', ' ')} = {top['object_value']}."


def retrieval_payload(service: RetrievalService, query: str, subject: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw = service.retrieve(query, top_k=5)
    memories = []
    evidence = []

    for item in raw:
        memory = item.memory
        if memory.subject != subject:
            continue

        memories.append(serialize_memory(memory))
        evidence.append({
            "memory_id": memory.id,
            "score": round(float(item.evidence.score), 6),
            "matched_fields": list(item.evidence.matched_fields),
            "evidence": item.evidence.evidence,
        })

    return memories, evidence


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "trustworthy-memory"}


@app.get("/api/memories")
def list_memories(db: Session = Depends(get_db)):
    service = MemoryService(db)
    return [serialize_memory(m) for m in service.list_active()]


@app.get("/api/memories/all")
def list_all_memories(db: Session = Depends(get_db)):
    service = MemoryService(db)
    return [serialize_memory(m) for m in service.list_all()]


@app.get("/api/memories/{memory_id}")
def get_memory(memory_id: str, db: Session = Depends(get_db)):
    service = MemoryService(db)
    try:
        return serialize_memory(service.get_memory(memory_id))
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/memories/{memory_id}/history")
def memory_history(memory_id: str, db: Session = Depends(get_db)):
    service = MemoryService(db)
    try:
        memory = service.get_memory(memory_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    records = service.repository.list_by_logical_key(memory.subject, memory.predicate)
    records = sorted(records, key=lambda item: (item.created_at, item.id))
    return [serialize_memory(item) for item in records]


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: str, db: Session = Depends(get_db)):
    service = MemoryService(db)
    try:
        deleted = service.delete_memory(memory_id, deleted_at=datetime.now(timezone.utc))
        db.commit()
        return serialize_memory(deleted)
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    message = request.message.strip()
    service = MemoryService(db)
    retrieval = RetrievalService(service.repository)

    # Questions use the existing deterministic retrieval engine.
    if is_question(message):
        memories, evidence = retrieval_payload(retrieval, message, request.subject)
        reply = make_answer(message, memories)
        return ChatResponse(
            reply=reply,
            action="retrieve",
            memories=memories,
            evidence=evidence,
        )

    # Definite statements are stored through the existing MemoryService.
    parsed = parse_statement(message)

    if parsed:
        subject, predicate, value = parsed
        source_id = f"chat-{uuid.uuid4()}"
        memory = service.create_memory(
            subject=subject,
            predicate=predicate,
            object_value=value,
            content=message,
            source_id=source_id,
            source_type="message",
        )
        db.commit()

        if memory.state.value == "active" and memory.supersedes_id:
            reply = (
                f"Updated your {predicate.replace('_', ' ')} to "
                f"{memory.object_value.title()}. "
                "The previous memory is preserved as superseded history."
            )
            action = "superseded"
        elif memory.state.value == "active":
            reply = (
                f"I'll remember that your "
                f"{predicate.replace('_', ' ')} is {memory.object_value.title()}."
            )
            action = "created"
        else:
            reply = "I kept the existing active memory because this statement was not a definite correction."
            action = "preserved"

        return ChatResponse(
            reply=reply,
            action=action,
            memory=serialize_memory(memory),
        )

    # Explicitly uncertain statements are not forced into the memory store.
    if re.search(r"\b(might|maybe|possibly|not sure|i think|could be|probably)\b", message.lower()):
        active = [serialize_memory(m) for m in service.list_active()]
        return ChatResponse(
            reply=(
                "I treated that statement as uncertain, so I did not replace "
                "an existing memory automatically."
            ),
            action="ambiguous",
            memories=active,
        )

    return ChatResponse(
        reply=(
            "I can remember definite facts such as where you live, where you work, "
            "your skills, languages, interests, role, phone, blood group, or favorite color. "
            "Try a clear statement or ask me about something I already know."
        ),
        action="none",
    )

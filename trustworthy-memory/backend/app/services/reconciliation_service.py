from dataclasses import dataclass
from typing import Optional

from app.domain.models import Memory
from app.domain.rules import (
    can_supersede,
    has_ambiguous_cue,
    has_explicit_correction_cue,
    is_same_logical_fact,
    should_preserve_as_ambiguous,
)
from app.domain.states import MemoryState


@dataclass(frozen=True)
class ReconciliationDecision:
    """
    Result of comparing a new candidate memory against an existing memory.
    """

    action: str
    existing_memory_id: Optional[str] = None
    reason: str = ""


class ReconciliationService:
    """
    Determines how a new memory relates to existing active memories.

    Important:
    This service does not modify the database. It only decides what
    should happen. Persistence is handled by MemoryService/Repository.
    """

    def decide(
        self,
        *,
        candidate_subject: str,
        candidate_predicate: str,
        candidate_content: str,
        existing_memory: Optional[Memory],
    ) -> ReconciliationDecision:

        if existing_memory is None:
            return ReconciliationDecision(
                action="create",
                reason="No existing memory for this logical fact.",
            )

        same_fact = is_same_logical_fact(
            candidate_subject,
            candidate_predicate,
            existing_memory.subject,
            existing_memory.predicate,
        )

        if not same_fact:
            return ReconciliationDecision(
                action="create",
                reason="Candidate targets a different logical fact.",
            )

        if existing_memory.state != MemoryState.ACTIVE:
            return ReconciliationDecision(
                action="create",
                reason="Existing memory is not active.",
            )

        explicit_correction = has_explicit_correction_cue(
            candidate_content
        )

        ambiguous_language = has_ambiguous_cue(
            candidate_content
        )

        if should_preserve_as_ambiguous(
            same_logical_fact=same_fact,
            explicit_correction=explicit_correction,
            ambiguous_language=ambiguous_language,
        ):
            return ReconciliationDecision(
                action="preserve_existing",
                existing_memory_id=existing_memory.id,
                reason=(
                    "Candidate contains uncertain language without "
                    "an explicit correction."
                ),
            )

        if can_supersede(
            existing_memory.state,
            same_logical_fact=same_fact,
            explicit_correction=explicit_correction,
        ):
            return ReconciliationDecision(
                action="supersede",
                existing_memory_id=existing_memory.id,
                reason="Explicit correction targets the same logical fact.",
            )

        return ReconciliationDecision(
            action="candidate",
            existing_memory_id=existing_memory.id,
            reason=(
                "Potential conflict detected without enough evidence "
                "for automatic supersession."
            ),
        )
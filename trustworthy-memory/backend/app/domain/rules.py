from dataclasses import dataclass
from typing import Optional

from .states import MemoryState
from .text import normalize_identifier, normalize_text


@dataclass(frozen=True)
class PredicateRule:
    """
    Defines how a logical predicate behaves.

    single_valued=True means a new explicit correction replaces the
    currently active value for that subject/predicate.

    single_valued=False means multiple values can coexist.
    """

    single_valued: bool


# Explicit registry keeps business behavior deterministic.
PREDICATE_RULES: dict[str, PredicateRule] = {
    "residence": PredicateRule(single_valued=True),
    "city": PredicateRule(single_valued=True),
    "current_city": PredicateRule(single_valued=True),
    "employer": PredicateRule(single_valued=True),
    "job_title": PredicateRule(single_valued=True),
    "phone": PredicateRule(single_valued=True),
    "email": PredicateRule(single_valued=True),
    "blood_group": PredicateRule(single_valued=True),
    "favorite_color": PredicateRule(single_valued=True),

    # Examples of facts that can legitimately have multiple values.
    "skill": PredicateRule(single_valued=False),
    "language": PredicateRule(single_valued=False),
    "interest": PredicateRule(single_valued=False),
}


DEFAULT_PREDICATE_RULE = PredicateRule(single_valued=True)


def get_predicate_rule(predicate: str) -> PredicateRule:
    normalized = normalize_identifier(predicate)
    return PREDICATE_RULES.get(normalized, DEFAULT_PREDICATE_RULE)


def is_single_valued(predicate: str) -> bool:
    return get_predicate_rule(predicate).single_valued


def logical_key(
    subject: str,
    predicate: str,
) -> str:
    """
    Identify the logical fact being represented.

    Example:
        user_1 + residence

    remains the same logical fact even when the value changes
    from Pune to Mumbai.
    """
    return "|".join(
        [
            normalize_identifier(subject),
            normalize_identifier(predicate),
        ]
    )


def active_key(
    subject: str,
    predicate: str,
    object_value: str,
) -> str:
    """
    Identify the active slot for a memory.

    Single-valued:
        subject|predicate

    Multi-valued:
        subject|predicate|object
    """
    normalized_subject = normalize_identifier(subject)
    normalized_predicate = normalize_identifier(predicate)
    normalized_object = normalize_text(object_value)

    if is_single_valued(normalized_predicate):
        return f"{normalized_subject}|{normalized_predicate}"

    return (
        f"{normalized_subject}|"
        f"{normalized_predicate}|"
        f"{normalized_object}"
    )


EXPLICIT_CORRECTION_CUES = (
    "actually",
    "correction",
    "correct that",
    "i meant",
    "i mean",
    "instead",
    "changed",
    "change my",
    "moved to",
    "now live in",
    "no longer",
)

AMBIGUOUS_CUES = (
    "maybe",
    "might",
    "possibly",
    "not sure",
    "i think",
    "could be",
    "probably",
)


def contains_cue(text: str, cues: tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    return any(cue in normalized for cue in cues)


def has_explicit_correction_cue(text: str) -> bool:
    return contains_cue(text, EXPLICIT_CORRECTION_CUES)


def has_ambiguous_cue(text: str) -> bool:
    return contains_cue(text, AMBIGUOUS_CUES)


def is_same_logical_fact(
    subject: str,
    predicate: str,
    other_subject: str,
    other_predicate: str,
) -> bool:
    return logical_key(subject, predicate) == logical_key(
        other_subject,
        other_predicate,
    )


def can_supersede(
    existing_state: MemoryState,
    *,
    same_logical_fact: bool,
    explicit_correction: bool,
) -> bool:
    """
    Decide whether a new memory may supersede an existing memory.

    Supersession is intentionally conservative:
    - Existing memory must be ACTIVE.
    - Facts must belong to the same logical predicate.
    - The new statement must contain an explicit correction signal.
    """
    return (
        existing_state == MemoryState.ACTIVE
        and same_logical_fact
        and explicit_correction
    )


def validate_state_transition(
    current_state: MemoryState,
    new_state: MemoryState,
) -> bool:
    """
    Validate lifecycle transitions.

    ACTIVE -> SUPERSEDED
    ACTIVE -> DELETED

    SUPERSEDED and DELETED are terminal states.
    """
    allowed = {
        MemoryState.ACTIVE: {
            MemoryState.SUPERSEDED,
            MemoryState.DELETED,
        },
        MemoryState.SUPERSEDED: set(),
        MemoryState.DELETED: set(),
    }

    return new_state in allowed[current_state]


def should_preserve_as_ambiguous(
    *,
    same_logical_fact: bool,
    explicit_correction: bool,
    ambiguous_language: bool,
) -> bool:
    """
    Conservative contradiction rule.

    If a statement targets the same logical fact but is uncertain and does
    not explicitly correct the existing fact, preserve the existing memory
    instead of automatically superseding it.
    """
    return (
        same_logical_fact
        and ambiguous_language
        and not explicit_correction
    )


def normalize_memory_fields(
    subject: str,
    predicate: str,
    object_value: str,
) -> tuple[str, str, str]:
    return (
        normalize_identifier(subject),
        normalize_identifier(predicate),
        normalize_text(object_value),
    )


def ensure_supported_state(state: Optional[MemoryState]) -> MemoryState:
    if state is None:
        return MemoryState.ACTIVE

    if isinstance(state, MemoryState):
        return state

    return MemoryState(state)
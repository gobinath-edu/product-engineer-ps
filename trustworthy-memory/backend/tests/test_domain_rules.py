from app.domain.rules import (
    active_key,
    has_ambiguous_cue,
    has_explicit_correction_cue,
    is_single_valued,
    logical_key,
    normalize_memory_fields,
    should_preserve_as_ambiguous,
    validate_state_transition,
)
from app.domain.states import MemoryState


def test_normalize_memory_fields():
    result = normalize_memory_fields(
        " User 1 ",
        " Residence ",
        "  Pune  ",
    )

    assert result == ("user_1", "residence", "pune")


def test_logical_key_does_not_change_when_value_changes():
    pune_key = logical_key("user_1", "residence")
    mumbai_key = logical_key("user_1", "residence")

    assert pune_key == mumbai_key


def test_single_valued_predicate():
    assert is_single_valued("residence")
    assert is_single_valued("city")


def test_multi_valued_predicate():
    assert not is_single_valued("skill")
    assert not is_single_valued("language")


def test_single_valued_active_key_ignores_object_value():
    pune_key = active_key("user_1", "residence", "Pune")
    mumbai_key = active_key("user_1", "residence", "Mumbai")

    assert pune_key == mumbai_key


def test_multi_valued_active_key_includes_object_value():
    python_key = active_key("user_1", "skill", "Python")
    java_key = active_key("user_1", "skill", "Java")

    assert python_key != java_key


def test_explicit_correction_is_detected():
    assert has_explicit_correction_cue(
        "Actually, I moved to Mumbai."
    )


def test_ambiguous_language_is_detected():
    assert has_ambiguous_cue(
        "I might be staying in Chennai this week."
    )


def test_ambiguous_statement_is_preserved():
    assert should_preserve_as_ambiguous(
        same_logical_fact=True,
        explicit_correction=False,
        ambiguous_language=True,
    )


def test_explicit_correction_is_not_ambiguous():
    assert not should_preserve_as_ambiguous(
        same_logical_fact=True,
        explicit_correction=True,
        ambiguous_language=True,
    )


def test_active_can_be_superseded():
    assert validate_state_transition(
        MemoryState.ACTIVE,
        MemoryState.SUPERSEDED,
    )


def test_active_can_be_deleted():
    assert validate_state_transition(
        MemoryState.ACTIVE,
        MemoryState.DELETED,
    )


def test_superseded_is_terminal():
    assert not validate_state_transition(
        MemoryState.SUPERSEDED,
        MemoryState.ACTIVE,
    )


def test_deleted_is_terminal():
    assert not validate_state_transition(
        MemoryState.DELETED,
        MemoryState.ACTIVE,
    )
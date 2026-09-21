import re
import unicodedata


def normalize_text(value: str) -> str:
    """
    Normalize text for deterministic comparison and retrieval.

    The original user-facing content is preserved separately in Memory.content.
    """
    if value is None:
        return ""

    value = unicodedata.normalize("NFKC", value)
    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)

    return value


def normalize_identifier(value: str) -> str:
    """
    Normalize identifiers such as subjects, predicates, and source IDs.
    """
    return normalize_text(value).replace(" ", "_")
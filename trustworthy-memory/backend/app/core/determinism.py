import hashlib
import uuid
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def stable_id(*parts: str) -> str:
    """
    Generate a deterministic UUID from stable input parts.

    The same inputs always produce the same ID, which is useful for
    deterministic fixtures and repeatable benchmark runs.
    """
    normalized = "|".join(str(part).strip() for part in parts)

    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            normalized,
        )
    )


def content_hash(*parts: str) -> str:
    """
    Generate a deterministic SHA-256 hash from supplied values.
    """
    normalized = "|".join(str(part).strip() for part in parts)

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()
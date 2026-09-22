from dataclasses import dataclass


@dataclass(frozen=True)
class Provenance:
    """
    Identifies the source from which a memory originated.
    """

    source_id: str
    source_type: str


class ProvenanceService:
    """
    Validates and constructs provenance information.

    Keeping provenance logic separate makes the source relationship
    explicit and testable.
    """

    ALLOWED_SOURCE_TYPES = {
        "message",
        "fixture",
        "import",
        "system",
    }

    def create(
        self,
        source_id: str,
        source_type: str = "message",
    ) -> Provenance:
        source_id = source_id.strip()
        source_type = source_type.strip().lower()

        if not source_id:
            raise ValueError("source_id must not be empty")

        if source_type not in self.ALLOWED_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported source_type: {source_type}"
            )

        return Provenance(
            source_id=source_id,
            source_type=source_type,
        )
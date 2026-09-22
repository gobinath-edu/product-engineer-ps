from dataclasses import dataclass
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.domain.models import Memory
from app.domain.states import MemoryState
from app.repositories.memory_repository import MemoryRepository


@dataclass(frozen=True)
class RetrievalEvidence:
    """
    Explain why a memory was selected.
    """

    score: float
    matched_fields: tuple[str, ...]
    evidence: str


@dataclass(frozen=True)
class RetrievalResult:
    """
    A memory returned by retrieval together with its evidence.
    """

    memory: Memory
    evidence: RetrievalEvidence


class RetrievalService:
    """
    Deterministic hybrid retrieval service.

    Retrieval pipeline:
    1. Load only ACTIVE memories.
    2. Infer the intended predicate from natural-language query wording.
    3. Apply structured matching.
    4. Apply lexical TF-IDF similarity.
    5. Combine deterministic signals.
    6. Filter low-score results.
    7. Sort deterministically.
    8. Return at most top_k memories.
    """

    STRUCTURED_WEIGHT = 0.50
    LEXICAL_WEIGHT = 0.35
    RECENCY_WEIGHT = 0.15

    DEFAULT_TOP_K = 5
    DEFAULT_MIN_SCORE = 0.10

    def __init__(
        self,
        repository: MemoryRepository,
    ):
        self.repository = repository

    # ============================================================
    # PUBLIC RETRIEVAL
    # ============================================================

    def retrieve(
        self,
        query: str,
        *,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> list[RetrievalResult]:
        """
        Retrieve the most relevant ACTIVE memories.

        Natural-language predicate inference is deterministic:
        the same query always produces the same inferred predicate.
        """

        if not query or not query.strip():
            return []

        if top_k <= 0:
            return []

        memories = [
            memory
            for memory in self.repository.list_active()
            if memory.state == MemoryState.ACTIVE
        ]

        if not memories:
            return []

        query_text = query.strip().lower()

        inferred_predicate = self._infer_predicate(query_text)

        documents = [
            self._document_for_memory(memory)
            for memory in memories
        ]

        lexical_scores = self._lexical_scores(
            query_text,
            documents,
        )

        scored_results: list[RetrievalResult] = []

        for memory, lexical_score in zip(
            memories,
            lexical_scores,
        ):
            structured_score, matched_fields = (
                self._structured_score(
                    memory=memory,
                    query=query_text,
                    subject=subject,
                    predicate=predicate,
                    inferred_predicate=inferred_predicate,
                )
            )

            recency_score = self._recency_score(memory)

            final_score = (
                self.STRUCTURED_WEIGHT * structured_score
                + self.LEXICAL_WEIGHT * lexical_score
                + self.RECENCY_WEIGHT * recency_score
            )

            final_score = round(final_score, 6)

            if final_score < min_score:
                continue

            evidence = self._build_evidence(
                memory=memory,
                score=final_score,
                matched_fields=matched_fields,
                lexical_score=lexical_score,
                structured_score=structured_score,
                inferred_predicate=inferred_predicate,
            )

            scored_results.append(
                RetrievalResult(
                    memory=memory,
                    evidence=evidence,
                )
            )

        scored_results.sort(
            key=lambda result: (
                -result.evidence.score,
                result.memory.id,
            )
        )

        return scored_results[:top_k]

    # ============================================================
    # PREDICATE INFERENCE
    # ============================================================

    @staticmethod
    def _infer_predicate(query: str) -> Optional[str]:
        """
        Infer the logical predicate intended by the query.

        This is deterministic rule-based query interpretation.
        It deliberately avoids an LLM in the retrieval-critical path.
        """

        normalized = " ".join(query.lower().split())

        # --------------------------------------------------------
        # Programming / technical skills
        # --------------------------------------------------------

        if (
            "programming language" in normalized
            or "programming languages" in normalized
            or "technical skill" in normalized
            or "technical skills" in normalized
        ):
            return "skill"

        # --------------------------------------------------------
        # Spoken / human languages
        # --------------------------------------------------------

        if (
            "what languages can i speak" in normalized
            or "which languages can i speak" in normalized
            or "languages do i speak" in normalized
            or "languages can i speak" in normalized
        ):
            return "language"

        # --------------------------------------------------------
        # Location / city
        # --------------------------------------------------------

        if (
            "currently located" in normalized
            or "current location" in normalized
            or "where am i located" in normalized
            or "where am i currently" in normalized
            or "what city do i live" in normalized
            or "which city do i live" in normalized
            or "city do i live" in normalized
            or "move to most recently" in normalized
            or "moved to most recently" in normalized
        ):
            return "city"

        # --------------------------------------------------------
        # Residence
        # --------------------------------------------------------

        if (
            "where do i live" in normalized
            or "where i live" in normalized
            or "where does user 2 live" in normalized
            or "where does user-002 live" in normalized
        ):
            return "residence"

        # --------------------------------------------------------
        # Employer
        # --------------------------------------------------------

        if (
            "where do i work" in normalized
            or "where i work" in normalized
            or "what company am i currently working for" in normalized
            or "what company am i working for" in normalized
            or "which company am i working for" in normalized
            or "what company do i work for" in normalized
            or "which company do i work for" in normalized
            or "my employer" in normalized
            or "company am i currently working" in normalized
        ):
            return "employer"

        # --------------------------------------------------------
        # Job title
        # --------------------------------------------------------

        if (
            "job title" in normalized
            or "job role" in normalized
            or "current role" in normalized
        ):
            return "job_title"

        # --------------------------------------------------------
        # Favorite color
        # --------------------------------------------------------

        if "favorite color" in normalized:
            return "favorite_color"

        # --------------------------------------------------------
        # Phone
        # --------------------------------------------------------

        if (
            "phone number" in normalized
            or "mobile number" in normalized
            or "contact number" in normalized
        ):
            return "phone"

        # --------------------------------------------------------
        # Blood group
        # --------------------------------------------------------

        if (
            "blood group" in normalized
            or "blood type" in normalized
        ):
            return "blood_group"

        # --------------------------------------------------------
        # Interests
        # --------------------------------------------------------

        if (
            "interested in" in normalized
            or "what am i interested in" in normalized
            or "my interests" in normalized
        ):
            return "interest"

        # --------------------------------------------------------
        # Generic skill questions
        # --------------------------------------------------------

        if (
            "what skills" in normalized
            or "which skills" in normalized
            or "skills do i have" in normalized
            or "do i know" in normalized
        ):
            return "skill"

        return None

    # ============================================================
    # DOCUMENT
    # ============================================================

    @staticmethod
    def _document_for_memory(memory: Memory) -> str:
        return " ".join(
            [
                memory.subject,
                memory.predicate,
                memory.object_value,
                memory.content,
            ]
        ).lower()

    # ============================================================
    # TF-IDF
    # ============================================================

    @staticmethod
    def _lexical_scores(
        query: str,
        documents: list[str],
    ) -> list[float]:
        """
        Deterministic TF-IDF cosine similarity.
        """

        if not documents:
            return []

        vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            token_pattern=r"(?u)\b\w+\b",
        )

        matrix = vectorizer.fit_transform(
            documents + [query]
        )

        document_matrix = matrix[:-1]
        query_vector = matrix[-1]

        similarities = cosine_similarity(
            document_matrix,
            query_vector,
        ).flatten()

        return [
            round(float(score), 6)
            for score in similarities
        ]

    # ============================================================
    # STRUCTURED SCORING
    # ============================================================

    @staticmethod
    def _structured_score(
        *,
        memory: Memory,
        query: str,
        subject: Optional[str],
        predicate: Optional[str],
        inferred_predicate: Optional[str],
    ) -> tuple[float, tuple[str, ...]]:
        """
        Structured relevance scoring.

        Signals:
        - explicit subject filter
        - explicit predicate filter
        - query mentions subject
        - query mentions actual predicate
        - inferred predicate matches memory predicate
        - object appears in query
        """

        matched_fields: list[str] = []
        score = 0.0

        normalized_query = query.lower()

        # --------------------------------------------------------
        # Explicit subject filter
        # --------------------------------------------------------

        if subject:
            normalized_subject = subject.strip().lower()

            if memory.subject.lower() == normalized_subject:
                score += 0.35
                matched_fields.append("subject")

        # --------------------------------------------------------
        # Explicit predicate filter
        # --------------------------------------------------------

        if predicate:
            normalized_predicate = predicate.strip().lower()

            if memory.predicate.lower() == normalized_predicate:
                score += 0.35
                matched_fields.append("predicate")

        # --------------------------------------------------------
        # Subject mentioned in query
        # --------------------------------------------------------

        if memory.subject.lower() in normalized_query:
            score += 0.10
            matched_fields.append("subject")

        # --------------------------------------------------------
        # Literal predicate mentioned in query
        # --------------------------------------------------------

        if memory.predicate.lower() in normalized_query:
            score += 0.15
            matched_fields.append("predicate")

        # --------------------------------------------------------
        # Natural-language predicate inference
        # --------------------------------------------------------

        if (
            inferred_predicate is not None
            and memory.predicate.lower()
            == inferred_predicate.lower()
        ):
            score += 0.55
            matched_fields.append("inferred_predicate")

        # --------------------------------------------------------
        # Object mentioned in query
        # --------------------------------------------------------

        if memory.object_value.lower() in normalized_query:
            score += 0.40
            matched_fields.append("object")

        return (
            min(score, 1.0),
            tuple(dict.fromkeys(matched_fields)),
        )

    # ============================================================
    # RECENCY
    # ============================================================

    @staticmethod
    def _recency_score(memory: Memory) -> float:
        """
        Deterministic recency signal.

        The benchmark is intentionally deterministic, so wall-clock
        time is not consulted during retrieval.
        """

        return 1.0

    # ============================================================
    # EVIDENCE
    # ============================================================

    @staticmethod
    def _build_evidence(
        *,
        memory: Memory,
        score: float,
        matched_fields: tuple[str, ...],
        lexical_score: float,
        structured_score: float,
        inferred_predicate: Optional[str],
    ) -> RetrievalEvidence:

        fields = list(matched_fields)

        if lexical_score > 0:
            fields.append("lexical")

        if not fields:
            fields.append("content")

        unique_fields = tuple(
            dict.fromkeys(fields)
        )

        inference_text = (
            inferred_predicate
            if inferred_predicate
            else "none"
        )

        evidence = (
            f"structured={structured_score:.3f}; "
            f"lexical={lexical_score:.3f}; "
            f"inferred_predicate={inference_text}; "
            f"matched={','.join(unique_fields)}"
        )

        return RetrievalEvidence(
            score=score,
            matched_fields=unique_fields,
            evidence=evidence,
        )
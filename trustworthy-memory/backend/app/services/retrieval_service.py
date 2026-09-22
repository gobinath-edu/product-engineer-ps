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
    2. Apply structured matching.
    3. Apply lexical TF-IDF similarity.
    4. Combine the signals into a deterministic score.
    5. Remove results below the relevance threshold.
    6. Sort deterministically.
    7. Return at most top_k memories.
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

        Results are deterministic because:
        - only ACTIVE memories are eligible;
        - TF-IDF input ordering is deterministic;
        - score rounding is deterministic;
        - ties are resolved using memory ID.
        """

        if not query.strip():
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
                    memory,
                    query_text,
                    subject,
                    predicate,
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

    @staticmethod
    def _lexical_scores(
        query: str,
        documents: list[str],
    ) -> list[float]:
        """
        Compute deterministic TF-IDF cosine similarity.

        If the vocabulary has no overlap with the query, every score
        is zero.
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

    @staticmethod
    def _structured_score(
        memory: Memory,
        query: str,
        subject: Optional[str],
        predicate: Optional[str],
    ) -> tuple[float, tuple[str, ...]]:
        """
        Calculate structured relevance.

        Matching fields:
        - explicit subject filter
        - explicit predicate filter
        - subject mentioned in query
        - predicate mentioned in query
        - object mentioned in query
        """

        matched_fields: list[str] = []
        score = 0.0

        normalized_query = query.lower()

        if subject:
            normalized_subject = subject.strip().lower()

            if memory.subject.lower() == normalized_subject:
                score += 0.35
                matched_fields.append("subject")

        if predicate:
            normalized_predicate = predicate.strip().lower()

            if memory.predicate.lower() == normalized_predicate:
                score += 0.35
                matched_fields.append("predicate")

        if memory.subject.lower() in normalized_query:
            score += 0.10
            matched_fields.append("subject")

        if memory.predicate.lower() in normalized_query:
            score += 0.15
            matched_fields.append("predicate")

        if memory.object_value.lower() in normalized_query:
            score += 0.40
            matched_fields.append("object")

        return min(score, 1.0), tuple(
            dict.fromkeys(matched_fields)
        )

    @staticmethod
    def _recency_score(memory: Memory) -> float:
        """
        Current memories are already lifecycle-filtered.

        For deterministic behavior we use a bounded constant here rather
        than depending on wall-clock time during retrieval.

        Recency can be expanded later if benchmark requirements require
        time-sensitive ranking.
        """

        return 1.0

    @staticmethod
    def _build_evidence(
        *,
        memory: Memory,
        score: float,
        matched_fields: tuple[str, ...],
        lexical_score: float,
        structured_score: float,
    ) -> RetrievalEvidence:
        fields = list(matched_fields)

        if lexical_score > 0:
            fields.append("lexical")

        if not fields:
            fields.append("content")

        unique_fields = tuple(dict.fromkeys(fields))

        evidence = (
            f"structured={structured_score:.3f}; "
            f"lexical={lexical_score:.3f}; "
            f"matched={','.join(unique_fields)}"
        )

        return RetrievalEvidence(
            score=score,
            matched_fields=unique_fields,
            evidence=evidence,
        )
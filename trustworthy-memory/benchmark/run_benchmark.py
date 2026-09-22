import json
import sys
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

FIXTURES_PATH = PROJECT_ROOT / "fixtures" / "memories.json"
QUERIES_PATH = PROJECT_ROOT / "benchmark" / "queries.json"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ============================================================
# BACKEND IMPORTS
# ============================================================

from app.db.database import (
    Base,
    SessionLocal,
    engine,
    initialize_database,
)

from app.repositories.memory_repository import MemoryRepository
from app.services.memory_service import MemoryService
from app.services.retrieval_service import RetrievalService


# ============================================================
# JSON LOADERS
# ============================================================

def load_json(path: Path):
    """Load JSON data from a file."""

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_memories():
    """Load benchmark fixture memories."""

    data = load_json(FIXTURES_PATH)

    if not isinstance(data, list):
        raise ValueError(
            "fixtures/memories.json must contain a JSON list."
        )

    return data


def load_queries():
    """Load deterministic benchmark queries."""

    data = load_json(QUERIES_PATH)

    if not isinstance(data, list):
        raise ValueError(
            "benchmark/queries.json must contain a JSON list."
        )

    return data


# ============================================================
# DATABASE RESET
# ============================================================

def reset_database() -> None:
    """
    Reset the SQLite database before every benchmark run.

    This guarantees that the benchmark starts from the same
    deterministic state every time.
    """

    print("=" * 70)
    print("RESETTING DATABASE")
    print("=" * 70)

    Base.metadata.drop_all(bind=engine)
    initialize_database()

    print("Database reset complete.")
    print()


# ============================================================
# SEED FIXTURES
# ============================================================

def seed_memories() -> int:
    """
    Insert fixture memories through the real MemoryService.

    This is important because the benchmark must exercise the
    actual memory reconciliation/lifecycle logic rather than
    inserting rows directly into the database.
    """

    memories = load_memories()

    print("=" * 70)
    print("SEEDING FIXTURE MEMORIES")
    print("=" * 70)

    with SessionLocal() as db:

        service = MemoryService(db)

        for item in memories:

            memory = service.create_memory(
                subject=item["subject"],
                predicate=item["predicate"],
                object_value=item["object_value"],
                content=item["content"],
                source_id=item["source_id"],
                source_type=item.get("source_type", "fixture"),
            )

            print(
                f"STORED | "
                f"{memory.subject}."
                f"{memory.predicate}="
                f"{memory.object_value} | "
                f"state={memory.state.value} | "
                f"id={memory.id}"
            )

        # Commit so the retrieval benchmark can use a fresh
        # database session and see the seeded memories.
        db.commit()

        repository = MemoryRepository(db)

        all_memories = repository.list_all()

        active_memories = [
            memory
            for memory in all_memories
            if memory.is_active()
        ]

        superseded_memories = [
            memory
            for memory in all_memories
            if memory.is_superseded()
        ]

        deleted_memories = [
            memory
            for memory in all_memories
            if memory.is_deleted()
        ]

    print()
    print("-" * 70)
    print("DATABASE SUMMARY")
    print("-" * 70)
    print(f"Fixture records      : {len(memories)}")
    print(f"Database records     : {len(all_memories)}")
    print(f"Active memories      : {len(active_memories)}")
    print(f"Superseded memories  : {len(superseded_memories)}")
    print(f"Deleted memories     : {len(deleted_memories)}")
    print("-" * 70)

    return len(memories)


# ============================================================
# MEMORY MATCHING
# ============================================================

def memory_matches_expected(memory, expected: str) -> bool:
    """
    Compare a returned memory against an expected benchmark value.

    Expected format:

        user-001.residence=chennai

    or:

        user-001.skill=python

    The comparison is performed against structured fields,
    not by searching a combined text string.
    """

    expected = str(expected).strip().lower()

    if "=" not in expected:
        return False

    logical_key, expected_object = expected.split("=", 1)

    if "." not in logical_key:
        return False

    expected_subject, expected_predicate = logical_key.split(
        ".",
        1,
    )

    return (
        memory["subject"].strip().lower()
        == expected_subject.strip().lower()
        and
        memory["predicate"].strip().lower()
        == expected_predicate.strip().lower()
        and
        memory["object_value"].strip().lower()
        == expected_object.strip().lower()
        and
        memory["state"].strip().lower()
        == "active"
    )


# ============================================================
# RUN RETRIEVAL BENCHMARK
# ============================================================

def run_benchmark() -> bool:
    """Run all deterministic retrieval queries."""

    queries = load_queries()

    print()
    print("=" * 70)
    print("RUNNING RETRIEVAL BENCHMARK")
    print("=" * 70)

    total_queries = len(queries)
    passed_queries = 0
    failed_queries = 0

    with SessionLocal() as db:

        repository = MemoryRepository(db)
        retrieval_service = RetrievalService(repository)

        for index, item in enumerate(queries, start=1):

            query_id = item["id"]
            query = item["query"]

            subject = item.get("subject")

            expected_include = item.get(
                "expected_include",
                [],
            )

            expected_exclude = item.get(
                "expected_exclude",
                [],
            )

            # ------------------------------------------------
            # RETRIEVE
            # ------------------------------------------------

            results = retrieval_service.retrieve(
                query=query,
                subject=subject,
            )

            # ------------------------------------------------
            # CONVERT RESULTS
            # ------------------------------------------------

            returned_memories = []

            for result in results:

                memory = result.memory

                returned_memories.append(
                    {
                        "id": memory.id,
                        "subject": memory.subject,
                        "predicate": memory.predicate,
                        "object_value": memory.object_value,
                        "content": memory.content,
                        "state": memory.state.value,
                        "matched_fields": (
                            result.evidence.matched_fields
                        ),
                        "score": result.evidence.score,
                    }
                )

            # ------------------------------------------------
            # CHECK INCLUSIONS
            # ------------------------------------------------

            missing = []

            for expected in expected_include:

                found = any(
                    memory_matches_expected(
                        memory,
                        expected,
                    )
                    for memory in returned_memories
                )

                if not found:
                    missing.append(expected)

            # ------------------------------------------------
            # CHECK EXCLUSIONS
            # ------------------------------------------------

            unexpected = []

            for excluded in expected_exclude:

                found = any(
                    memory_matches_expected(
                        memory,
                        excluded,
                    )
                    for memory in returned_memories
                )

                if found:
                    unexpected.append(excluded)

            # ------------------------------------------------
            # CHECK LIFECYCLE
            # ------------------------------------------------

            lifecycle_violations = []

            for memory in returned_memories:

                if memory["state"] != "active":

                    lifecycle_violations.append(
                        f"{memory['subject']}."
                        f"{memory['predicate']}="
                        f"{memory['object_value']} "
                        f"(state={memory['state']})"
                    )

            # ------------------------------------------------
            # CHECK RESULT
            # ------------------------------------------------

            passed = (
                len(missing) == 0
                and len(unexpected) == 0
                and len(lifecycle_violations) == 0
            )

            if passed:

                passed_queries += 1
                status = "PASS"

            else:

                failed_queries += 1
                status = "FAIL"

            # ------------------------------------------------
            # PRINT QUERY
            # ------------------------------------------------

            print()
            print("=" * 70)
            print(f"[{status}] {query_id}")
            print("=" * 70)

            print(f"Query: {query}")

            if subject:
                print(f"Subject: {subject}")

            print(
                f"Expected include: "
                f"{expected_include}"
            )

            print(
                f"Expected exclude: "
                f"{expected_exclude}"
            )

            # ------------------------------------------------
            # PRINT RESULTS
            # ------------------------------------------------

            if not returned_memories:

                print("Results: NO RESULTS")

            else:

                print("Results:")

                for memory in returned_memories:

                    matched = memory["matched_fields"]

                    print(
                        f"  - "
                        f"{memory['subject']}."
                        f"{memory['predicate']}="
                        f"{memory['object_value']} "
                        f"| score={memory['score']:.6f} "
                        f"| state={memory['state']} "
                        f"| matched={matched}"
                    )

            # ------------------------------------------------
            # PRINT FAILURES
            # ------------------------------------------------

            if missing:

                print(
                    f"Missing expected: {missing}"
                )

            if unexpected:

                print(
                    f"Unexpected results: {unexpected}"
                )

            if lifecycle_violations:

                print(
                    "Lifecycle violations: "
                    f"{lifecycle_violations}"
                )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    pass_rate = (
        (passed_queries / total_queries) * 100
        if total_queries > 0
        else 0.0
    )

    print()
    print("=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)

    print(f"Total queries : {total_queries}")
    print(f"Passed        : {passed_queries}")
    print(f"Failed        : {failed_queries}")
    print(f"Pass rate     : {pass_rate:.2f}%")

    print("=" * 70)

    if failed_queries == 0:

        print("BENCHMARK RESULT: PASS")

        return True

    else:

        print("BENCHMARK RESULT: FAIL")

        return False


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print("=" * 70)
    print("TRUSTWORTHY LONG-TERM MEMORY BENCHMARK")
    print("=" * 70)

    print(
        f"Project root : {PROJECT_ROOT}"
    )

    print(
        f"Fixtures     : {FIXTURES_PATH}"
    )

    print(
        f"Queries      : {QUERIES_PATH}"
    )

    print()

    # --------------------------------------------------------
    # Step 1: Reset database
    # --------------------------------------------------------

    reset_database()

    # --------------------------------------------------------
    # Step 2: Seed deterministic fixtures
    # --------------------------------------------------------

    fixture_count = seed_memories()

    print()
    print(
        f"Loaded {fixture_count} fixture records."
    )

    # --------------------------------------------------------
    # Step 3: Run benchmark
    # --------------------------------------------------------

    success = run_benchmark()

    # --------------------------------------------------------
    # Step 4: Exit correctly
    # --------------------------------------------------------

    if not success:

        raise SystemExit(1)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
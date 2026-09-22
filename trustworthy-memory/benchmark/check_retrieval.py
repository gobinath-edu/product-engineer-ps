import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.database import SessionLocal
from app.repositories.memory_repository import MemoryRepository
from app.services.retrieval_service import RetrievalService


QUERIES_PATH = PROJECT_ROOT / "benchmark" / "queries.json"


def load_queries():
    with QUERIES_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():
    queries = load_queries()

    with SessionLocal() as db:
        repository = MemoryRepository(db)
        service = RetrievalService(repository)

        for item in queries:
            results = service.retrieve(
                query=item["query"],
                subject=item["subject"],
            )

            print()
            print("=" * 70)
            print(f"{item['id']} | {item['query']}")
            print("=" * 70)

            if not results:
                print("NO RESULTS")
                continue

            for result in results:
                memory = result.memory
                evidence = result.evidence

                print(
                    f"{memory.subject}.{memory.predicate}="
                    f"{memory.object_value}"
                    f" | score={evidence.score:.6f}"
                    f" | state={memory.state.value}"
                    f" | matched={evidence.matched_fields}"
                )


if __name__ == "__main__":
    main()
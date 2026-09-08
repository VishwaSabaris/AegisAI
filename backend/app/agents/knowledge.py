from dataclasses import dataclass

from backend.app.core.database import SessionLocal
from backend.app.repositories.knowledge_repository import (
    KnowledgeRepository,
)
from backend.app.services.embedding import embed_text


@dataclass
class KnowledgeResult:
    """
    A single knowledge retrieval result.
    """

    chunk_id: int
    source: str
    title: str
    content: str
    similarity: float


class KnowledgeAgent:
    """
    AegisAI Knowledge Agent.

    Converts a natural-language query into an embedding,
    retrieves semantically relevant knowledge from pgvector,
    and returns structured results.

    The Knowledge Agent performs retrieval only.
    It does not execute infrastructure actions.
    """

    def retrieve(
        self,
        query: str,
        limit: int = 5,
    ) -> list[KnowledgeResult]:
        if not query.strip():
            raise ValueError("Knowledge query cannot be empty.")

        if limit < 1:
            raise ValueError("Retrieval limit must be at least 1.")

        query_embedding = embed_text(query)

        db = SessionLocal()

        try:
            repository = KnowledgeRepository(db)

            results = repository.search(
                embedding=query_embedding,
                limit=limit,
            )

            return [
                KnowledgeResult(
                    chunk_id=chunk.id,
                    source=chunk.source,
                    title=chunk.title,
                    content=chunk.content,
                    similarity=similarity,
                )
                for chunk, similarity in results
            ]

        finally:
            db.close()

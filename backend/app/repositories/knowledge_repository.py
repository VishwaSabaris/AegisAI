from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import KnowledgeChunk


class KnowledgeRepository:
    """
    Repository for AegisAI knowledge-base chunks.

    Handles persistence and vector similarity retrieval while
    keeping database operations isolated from the Knowledge Agent.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        source: str,
        title: str,
        content: str,
        embedding: list[float],
    ) -> KnowledgeChunk:
        chunk = KnowledgeChunk(
            source=source,
            title=title,
            content=content,
            embedding=embedding,
        )

        self.db.add(chunk)
        self.db.commit()
        self.db.refresh(chunk)

        return chunk

    def get_by_id(
        self,
        chunk_id: int,
    ) -> KnowledgeChunk | None:
        return self.db.get(KnowledgeChunk, chunk_id)

    def get_all(self) -> list[KnowledgeChunk]:
        statement = select(KnowledgeChunk).order_by(
            KnowledgeChunk.id.asc()
        )

        return list(self.db.scalars(statement).all())

    def search(
        self,
        embedding: list[float],
        limit: int = 5,
    ) -> list[tuple[KnowledgeChunk, float]]:
        """
        Retrieve the most semantically similar knowledge chunks.

        Returns each chunk together with its cosine similarity
        score. Higher scores indicate greater semantic similarity.
        """

        distance = KnowledgeChunk.embedding.cosine_distance(
            embedding
        )

        statement = (
            select(
                KnowledgeChunk,
                (1 - distance).label("similarity"),
            )
            .order_by(distance)
            .limit(limit)
        )

        results = self.db.execute(statement).all()

        return [
            (chunk, float(similarity))
            for chunk, similarity in results
        ]

    def delete(
        self,
        chunk_id: int,
    ) -> bool:
        chunk = self.get_by_id(chunk_id)

        if chunk is None:
            return False

        self.db.delete(chunk)
        self.db.commit()

        return True

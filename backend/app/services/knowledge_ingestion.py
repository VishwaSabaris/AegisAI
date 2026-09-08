from backend.app.core.database import SessionLocal
from backend.app.repositories.knowledge_repository import KnowledgeRepository
from backend.app.services.embedding import embed_text


def chunk_text(
    text: str,
) -> list[str]:
    """
    Split a knowledge document into non-empty paragraphs.

    Paragraph-based chunking is intentionally simple for the
    first AegisAI RAG implementation.
    """
    chunks = [
        chunk.strip()
        for chunk in text.split("\n\n")
        if chunk.strip()
    ]

    return chunks


def ingest_document(
    source: str,
    title: str,
    content: str,
) -> list[int]:
    """
    Chunk, embed, and persist a knowledge document.

    Returns the database IDs of the created knowledge chunks.
    """

    chunks = chunk_text(content)

    if not chunks:
        raise ValueError("Document content cannot be empty.")

    db = SessionLocal()

    try:
        repository = KnowledgeRepository(db)
        created_ids: list[int] = []

        for chunk in chunks:
            embedding = embed_text(chunk)

            record = repository.create(
                source=source,
                title=title,
                content=chunk,
                embedding=embedding,
            )

            created_ids.append(record.id)

        return created_ids

    finally:
        db.close()

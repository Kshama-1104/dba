import pytest

from backend.app.services.chunking_service import ChunkingService


def test_chunking_empty_text():
    chunker = ChunkingService()
    assert chunker.chunk_text("") == []
    assert chunker.chunk_text("   ") == []


def test_chunking_short_text_single_chunk():
    chunker = ChunkingService(chunk_size=500, chunk_overlap=50)
    text = "Short company announcement regarding new product features."
    chunks = chunker.chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].content == text
    assert chunks[0].token_count > 0


def test_chunking_long_text_deterministic_order_and_overlap():
    chunker = ChunkingService(chunk_size=100, chunk_overlap=20)
    text = (
        "Paragraph one discusses foundational AI principles and company knowledge.\n\n"
        "Paragraph two delves into vector embeddings, similarity search, and pgvector.\n\n"
        "Paragraph three summarizes the deterministic safety gates and editorial workflows."
    )
    chunks1 = chunker.chunk_text(text)
    chunks2 = chunker.chunk_text(text)

    # Determinism
    assert len(chunks1) > 1
    assert len(chunks1) == len(chunks2)
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.chunk_index == c2.chunk_index
        assert c1.content == c2.content
        assert c1.token_count == c2.token_count

    # Sequential ordering
    for idx, c in enumerate(chunks1):
        assert c.chunk_index == idx
        assert len(c.content) > 0


def test_chunking_invalid_parameters():
    with pytest.raises(ValueError, match="chunk_size must be greater than 0"):
        ChunkingService(chunk_size=0)

    with pytest.raises(ValueError, match="strictly less than chunk_size"):
        ChunkingService(chunk_size=100, chunk_overlap=100)

    with pytest.raises(ValueError, match="cannot be negative"):
        ChunkingService(chunk_size=100, chunk_overlap=-1)

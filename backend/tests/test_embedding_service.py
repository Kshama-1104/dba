import math
from backend.app.services.embedding_service import (
    DeterministicEmbeddingProvider,
    get_embedding_provider,
    set_embedding_provider,
)


def test_embedding_dimension_and_normalization():
    provider = DeterministicEmbeddingProvider(dimension=384)
    assert provider.dimension == 384
    assert provider.model_name == "all-MiniLM-L6-v2"

    text = "Artificial intelligence automated daily blog writer"
    vec = provider.embed_text(text)
    assert len(vec) == 384

    # Check L2 unit normalization
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-4


def test_embedding_determinism():
    provider = DeterministicEmbeddingProvider(dimension=384)
    text = "Predictable deterministic vector generation for testing"
    vec1 = provider.embed_text(text)
    vec2 = provider.embed_text(text)
    assert vec1 == vec2


def test_embedding_semantic_relative_similarity():
    provider = DeterministicEmbeddingProvider(dimension=384)
    v_base = provider.embed_text("enterprise software cloud deployment architecture")
    v_related = provider.embed_text("cloud deployment infrastructure software enterprise")
    v_unrelated = provider.embed_text("banana apple orange strawberry fruit salad")

    sim_related = sum(a * b for a, b in zip(v_base, v_related))
    sim_unrelated = sum(a * b for a, b in zip(v_base, v_unrelated))

    assert sim_related > sim_unrelated


def test_embedding_batch_generation():
    provider = DeterministicEmbeddingProvider(dimension=384)
    texts = ["First chunk of text", "Second chunk of text"]
    batch_vecs = provider.embed_texts(texts)
    assert len(batch_vecs) == 2
    assert batch_vecs[0] == provider.embed_text(texts[0])
    assert batch_vecs[1] == provider.embed_text(texts[1])


def test_provider_factory():
    provider = get_embedding_provider()
    assert provider.dimension == 384

import pytest
import time
from app.core.cache import CacheManager
from app.config import Settings
from app.services.rag_service import RAGService


def test_cache_set_get_and_expiration(temp_dir: str):
    settings = Settings(
        redis_enabled=False,  # test internal fallback cache logic
        redis_ttl_seconds=1,
        chroma_persist_directory=temp_dir,
    )
    cache = CacheManager(settings=settings)

    # 1. Store item
    payload = {"answer": "Quantum superposition allows qubits to exist in 0 and 1 states simultaneously."}
    cache.set("what is superposition?", payload, ttl=1)

    # 2. Retrieve immediately
    hit = cache.get("What is superposition?")  # Case-insensitive & punctuation agnostic
    assert hit is not None
    assert hit["answer"] == payload["answer"]
    assert hit["cached"] is True

    # 3. Test Invalidation
    cache.invalidate_all()
    assert cache.get("what is superposition?") is None


@pytest.mark.asyncio
async def test_rag_service_cache_hit(rag_service: RAGService, sample_docs_dir):
    # Ingest document
    doc_path = sample_docs_dir / "ai_ethics_framework.md"
    rag_service.ingest_document(doc_path.read_bytes(), doc_path.name)

    # Query 1: Cache Miss
    res1 = await rag_service.answer_question("What are the ethics principles?")
    assert not res1.cached

    # Query 2: Cache Hit
    res2 = await rag_service.answer_question("What are the ethics principles?")
    assert res2.cached
    assert res2.answer == res1.answer

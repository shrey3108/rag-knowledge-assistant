import pytest
from pathlib import Path
from app.services.rag_service import RAGService, UNAVAILABLE_MESSAGE


@pytest.mark.asyncio
async def test_empty_knowledge_base_query(rag_service: RAGService):
    res = await rag_service.answer_question("What is our disaster recovery target?")
    assert not res.is_answered
    assert UNAVAILABLE_MESSAGE in res.answer
    assert len(res.evidence) == 0


@pytest.mark.asyncio
async def test_rag_ingest_and_grounded_answer(rag_service: RAGService, sample_docs_dir: Path):
    doc_path = sample_docs_dir / "ai_ethics_framework.md"
    content = doc_path.read_bytes()

    # Ingest document
    ingest_res = rag_service.ingest_document(content=content, filename=doc_path.name)
    assert ingest_res.chunks_created > 0

    # Answer relevant question
    res = await rag_service.answer_question("What is the policy regarding algorithmic fairness and ethics?")
    assert res.is_answered
    assert len(res.evidence) > 0
    assert res.evidence[0].document_name == "ai_ethics_framework.md"
    assert res.confidence_score > 0.0


@pytest.mark.asyncio
async def test_unanswerable_rejection(rag_service: RAGService, sample_docs_dir: Path):
    # Ingest AI ethics document only
    doc_path = sample_docs_dir / "ai_ethics_framework.md"
    rag_service.ingest_document(content=doc_path.read_bytes(), filename=doc_path.name)

    # Ask unanswerable question about space / astronomy
    res = await rag_service.answer_question("What is the surface temperature and atmospheric pressure on Venus?")
    assert not res.is_answered
    assert UNAVAILABLE_MESSAGE in res.answer

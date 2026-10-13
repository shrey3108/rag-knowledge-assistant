import pytest
from app.core.vector_store import VectorStore
from app.core.chunker import DocumentChunk


def test_vector_store_crud(vector_store: VectorStore):
    chunks = [
        DocumentChunk(
            chunk_id="doc1_p1_c1",
            document_name="doc1.txt",
            page_number=1,
            chunk_index=1,
            text="Artificial intelligence safety requires strict human oversight.",
            char_count=65,
        ),
        DocumentChunk(
            chunk_id="doc2_p1_c1",
            document_name="doc2.txt",
            page_number=1,
            chunk_index=1,
            text="Cloud databases must support automated failover within 15 minutes.",
            char_count=67,
        ),
    ]

    # Generate test embeddings (normalized vectors)
    vec1 = [0.9, 0.1, 0.0] + [0.0] * 381
    vec2 = [0.0, 0.1, 0.9] + [0.0] * 381

    # 1. Add chunks
    added = vector_store.add_chunks(chunks, [vec1, vec2])
    assert added == 2

    # 2. Check stats & list docs
    stats = vector_store.get_stats()
    assert stats["total_chunks"] == 2
    assert stats["total_documents"] == 2

    docs = vector_store.list_documents()
    doc_names = [d["document_name"] for d in docs]
    assert "doc1.txt" in doc_names
    assert "doc2.txt" in doc_names

    # 3. Search closest to vec1
    query_vec = [0.95, 0.05, 0.0] + [0.0] * 381
    results = vector_store.similarity_search(query_vec, top_k=2)
    assert len(results) > 0
    assert results[0].document_name == "doc1.txt"
    assert results[0].similarity_score > 0.8

    # 4. Delete document
    deleted = vector_store.delete_document("doc1.txt")
    assert deleted == 1
    assert vector_store.get_stats()["total_chunks"] == 1

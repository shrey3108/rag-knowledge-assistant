import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.chunker import DocumentChunk

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    chunk_id: str
    document_name: str
    page_number: int
    chunk_index: int
    text: str
    similarity_score: float  # Normalized cosine similarity in range [0, 1]


class VectorStore:
    """Persistent ChromaDB vector store with cosine similarity."""

    def __init__(self, persist_dir: str = "./data/chroma_db", collection_name: str = "knowledge_base"):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        os.makedirs(self.persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> int:
        """Upsert chunks and embeddings into the collection."""
        if not chunks:
            return 0

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "document_name": c.document_name,
                "page_number": c.page_number,
                "chunk_index": c.chunk_index,
                "char_count": c.char_count,
            }
            for c in chunks
        ]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(f"Upserted {len(chunks)} chunks into ChromaDB collection '{self.collection_name}'.")
        return len(chunks)

    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 4,
        score_threshold: Optional[float] = None
    ) -> List[SearchResult]:
        """Perform semantic search using query embedding vector."""
        total_items = self.collection.count()
        if total_items == 0:
            return []

        n_results = min(top_k, total_items)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        search_results: List[SearchResult] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return search_results

        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else []
        metas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        for i in range(len(ids)):
            # For cosine distance in Chroma: similarity = 1 - distance
            dist = distances[i] if i < len(distances) else 1.0
            similarity = max(0.0, min(1.0, 1.0 - dist))

            if score_threshold is not None and similarity < score_threshold:
                continue

            meta = metas[i] if i < len(metas) else {}
            search_results.append(
                SearchResult(
                    chunk_id=ids[i],
                    document_name=meta.get("document_name", "unknown"),
                    page_number=meta.get("page_number", 1),
                    chunk_index=meta.get("chunk_index", 0),
                    text=docs[i] if i < len(docs) else "",
                    similarity_score=round(similarity, 4),
                )
            )

        return search_results

    def list_documents(self) -> List[Dict[str, Any]]:
        """List distinct documents with their chunk count and page statistics."""
        data = self.collection.get(include=["metadatas"])
        metas = data.get("metadatas", []) or []

        doc_stats: Dict[str, Dict[str, Any]] = {}
        for m in metas:
            doc_name = m.get("document_name", "unknown")
            page_num = m.get("page_number", 1)
            if doc_name not in doc_stats:
                doc_stats[doc_name] = {
                    "document_name": doc_name,
                    "chunk_count": 0,
                    "pages": set(),
                }
            doc_stats[doc_name]["chunk_count"] += 1
            doc_stats[doc_name]["pages"].add(page_num)

        return [
            {
                "document_name": k,
                "chunk_count": v["chunk_count"],
                "total_pages": len(v["pages"]),
            }
            for k, v in doc_stats.items()
        ]

    def delete_document(self, document_name: str) -> int:
        """Delete all chunks belonging to a document."""
        data = self.collection.get(where={"document_name": document_name})
        ids_to_delete = data.get("ids", [])
        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)
        return len(ids_to_delete)

    def clear_all(self) -> None:
        """Delete and recreate collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def get_stats(self) -> Dict[str, Any]:
        """Return total chunks and indexed documents."""
        docs = self.list_documents()
        return {
            "total_chunks": self.collection.count(),
            "total_documents": len(docs),
            "collection_name": self.collection_name,
            "persist_directory": self.persist_dir,
        }

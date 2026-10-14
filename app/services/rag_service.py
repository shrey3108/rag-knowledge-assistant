import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core.document_parser import DocumentParser, ParsedDocument
from app.core.chunker import RecursiveChunker, DocumentChunk
from app.core.embedding import EmbeddingService
from app.core.vector_store import VectorStore, SearchResult
from app.core.cache import CacheManager
from app.core.session import SessionManager
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

UNAVAILABLE_MESSAGE = "The provided documents do not contain sufficient information to answer this question."


class EvidenceItem(BaseModel):
    document_name: str
    page_number: int
    chunk_id: str
    excerpt: str
    similarity_score: float


class AnswerResult(BaseModel):
    question: str
    answer: str
    is_answered: bool
    evidence: List[EvidenceItem]
    confidence_score: float
    retrieved_chunks_count: int
    cached: bool = False
    session_id: Optional[str] = None
    document_filter: Optional[str] = None




class IngestionResult(BaseModel):
    filename: str
    file_type: str
    total_pages: int
    chunks_created: int
    message: str


class RAGService:
    """Orchestrates document ingestion, vector retrieval, grounded prompt construction, and citation generation."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None,
        cache: Optional[CacheManager] = None,
    ):
        self.settings = settings or get_settings()
        self.vector_store = vector_store or VectorStore(
            persist_dir=self.settings.chroma_persist_directory,
            collection_name=self.settings.collection_name,
        )
        self.embedding_service = embedding_service or EmbeddingService.get_instance(
            model_name=self.settings.embedding_model
        )
        self.llm_service = llm_service or LLMService(settings=self.settings)
        self.cache = cache or CacheManager.get_instance(settings=self.settings)
        self.chunker = RecursiveChunker(
            chunk_size=self.settings.max_chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )

    @staticmethod
    def is_conversational_greeting(query: str) -> bool:
        normalized = re.sub(r"[^\w\s]", "", query.strip().lower())
        greetings = {
            "hi", "hello", "hey", "hola", "namaste", "good morning", "good evening",
            "good afternoon", "howdy", "wassup", "what's up", "whats up", "how are you",
            "who are you", "what can you do", "help", "kya kar sakte ho", "kaise ho"
        }
        return normalized in greetings or normalized.startswith(("hi ", "hello ", "hey "))

    def ingest_document(self, content: bytes, filename: str) -> IngestionResult:
        """Parse, chunk, embed, and store a document with SHA-256 duplicate detection."""
        # 1. Parse document and compute content hash
        parsed_doc: ParsedDocument = DocumentParser.parse_bytes(content, filename)

        # Check duplicate by content hash (inspired by previous repo)
        existing_doc = self.vector_store.has_file_hash(parsed_doc.file_hash)
        if existing_doc and existing_doc == filename:
            logger.info(f"Duplicate file detected: '{filename}' has identical SHA256 hash. Skipping re-embedding.")
            return IngestionResult(
                filename=filename,
                file_type=parsed_doc.file_type,
                total_pages=parsed_doc.total_pages,
                chunks_created=0,
                message=f"Duplicate file detected: '{filename}' with identical SHA256 content is already indexed. Redundant embedding skipped.",
            )

        # 2. Chunk document
        chunks: List[DocumentChunk] = self.chunker.chunk_document(parsed_doc)
        if not chunks:
            raise ValueError(f"Document '{filename}' could not be chunked or contained no readable text.")

        # 3. Generate embeddings
        texts = [c.text for c in chunks]
        embeddings = self.embedding_service.embed_texts(texts)

        # 4. Upsert into vector store (deletes older chunks of same doc first for clean update)
        self.vector_store.delete_document(filename)
        self.vector_store.add_chunks(chunks, embeddings)

        # 5. Invalidate query cache so stale answers are flushed
        self.cache.invalidate_all()

        return IngestionResult(
            filename=filename,
            file_type=parsed_doc.file_type,
            total_pages=parsed_doc.total_pages,
            chunks_created=len(chunks),
            message=f"Successfully ingested '{filename}' ({len(chunks)} chunks, {parsed_doc.total_pages} page(s)).",
        )

    async def answer_question(
        self,
        question: str,
        document_name: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AnswerResult:
        """Retrieve relevant context and generate grounded answer with citations, optional document filter, and session history."""
        clean_query = question.strip()
        if not clean_query:
            return AnswerResult(
                question=question,
                answer="Question cannot be empty.",
                is_answered=False,
                evidence=[],
                confidence_score=0.0,
                retrieved_chunks_count=0,
                session_id=session_id,
                document_filter=document_name,
            )

        # 0. Check cache (scoped by document filter if active)
        cache_query_key = f"{document_name or 'all'}::{clean_query}"
        cached_payload = self.cache.get(cache_query_key)
        if cached_payload:
            return AnswerResult(**cached_payload)

        # 1. Handle Conversational Greetings & Small Talk
        if self.is_conversational_greeting(clean_query):
            docs = self.vector_store.list_documents()
            doc_names = [d["document_name"] for d in docs]
            doc_list_str = ", ".join(doc_names) if doc_names else "no documents indexed yet"

            system_prompt = (
                "You are an articulate, friendly, and helpful AI Knowledge Assistant powered by a 120B model.\n"
                f"You have direct access to a knowledge base containing the following indexed documents: {doc_list_str}.\n"
                "Respond warmly, politely, and concisely to the user's greeting or question about your capabilities. "
                "Introduce yourself, mention that you can answer questions grounded in their uploaded documents, "
                "and invite them to ask anything."
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": clean_query},
            ]
            try:
                greeting_reply = await self.llm_service.generate_response(messages=messages, temperature=0.3)
            except Exception as e:
                logger.warning(f"LLM greeting generation error: {e}")
                greeting_reply = (
                    f"Hello! I am your AI Knowledge Assistant. I'm ready to answer any questions "
                    f"from your indexed documents ({doc_list_str}). What would you like to explore?"
                )

            res = AnswerResult(
                question=question,
                answer=greeting_reply,
                is_answered=True,
                evidence=[],
                confidence_score=1.0,
                retrieved_chunks_count=0,
                cached=False,
                session_id=session_id,
                document_filter=document_name,
            )
            self.cache.set(cache_query_key, res.model_dump())
            if session_id:
                SessionManager.get_instance().add_message(session_id, "user", clean_query)
                SessionManager.get_instance().add_message(session_id, "assistant", greeting_reply)
            return res

        # Check if any documents exist in vector store
        stats = self.vector_store.get_stats()
        if stats["total_chunks"] == 0:
            return AnswerResult(
                question=question,
                answer=f"{UNAVAILABLE_MESSAGE} (No documents have been indexed yet.)",
                is_answered=False,
                evidence=[],
                confidence_score=0.0,
                retrieved_chunks_count=0,
                session_id=session_id,
                document_filter=document_name,
            )

        # 1. Embed query
        query_embedding = self.embedding_service.embed_query(clean_query)

        # 2. Retrieve top_k chunks (optionally scoped to a document)
        raw_results: List[SearchResult] = self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=self.settings.top_k,
            score_threshold=None,
            filter_document=document_name,
        )

        # Filter by similarity threshold
        filtered_results = [
            r for r in raw_results if r.similarity_score >= self.settings.similarity_threshold
        ]

        # If no chunks passed threshold, reject immediately without wasting LLM call
        if not filtered_results:
            logger.info(
                f"Query '{clean_query}' yielded no chunks above threshold {self.settings.similarity_threshold}."
            )
            return AnswerResult(
                question=question,
                answer=UNAVAILABLE_MESSAGE,
                is_answered=False,
                evidence=[],
                confidence_score=raw_results[0].similarity_score if raw_results else 0.0,
                retrieved_chunks_count=0,
                session_id=session_id,
                document_filter=document_name,
            )

        # Build evidence items
        evidence_items: List[EvidenceItem] = [
            EvidenceItem(
                document_name=r.document_name,
                page_number=r.page_number,
                chunk_id=r.chunk_id,
                excerpt=r.text,
                similarity_score=r.similarity_score,
            )
            for r in filtered_results
        ]

        # 3. Construct grounded prompt
        context_blocks = []
        for idx, item in enumerate(evidence_items, start=1):
            context_blocks.append(
                f"[Source #{idx}: {item.document_name} | Page {item.page_number}]\n{item.excerpt}"
            )
        formatted_context = "\n\n".join(context_blocks)

        system_prompt = (
            "You are a rigorous, truthful AI knowledge assistant.\n"
            "Your objective is to answer the user's question using ONLY the provided document excerpts.\n\n"
            "STRICT RULES:\n"
            "1. Answer strictly based on the provided context. Do NOT invent, assume, or extrapolate facts.\n"
            f"2. If the context does not explicitly contain the necessary information to answer the question, you MUST respond exactly: '{UNAVAILABLE_MESSAGE}'\n"
            "3. Cite your sources in the text using [Document: <filename>, Page: <page>] format wherever you reference facts.\n"
            "4. Keep answers concise, factual, and direct."
        )

        user_prompt = (
            f"DOCUMENT CONTEXT:\n{formatted_context}\n\n"
            f"QUESTION:\n{clean_query}\n\n"
            "Grounded Answer (remember: if the info is not in the context, say information is unavailable):"
        )

        # Multi-turn history injection
        history_turns = []
        if session_id:
            history_turns = SessionManager.get_instance().get_history(session_id, limit=4)

        messages = [
            {"role": "system", "content": system_prompt},
            *history_turns,
            {"role": "user", "content": user_prompt},
        ]

        # 4. Generate answer via LLM
        try:
            llm_response = await self.llm_service.generate_response(messages=messages, temperature=0.0)
        except Exception as e:
            logger.error(f"Error during LLM generation: {e}")
            llm_response = f"Error generating answer from LLM: {str(e)}"

        # 5. Check reliability & unanswerable cues
        is_answered = True
        negative_indicators = [
            UNAVAILABLE_MESSAGE.lower(),
            "not contain sufficient information",
            "information is unavailable",
            "not mentioned in the provided",
            "does not provide information",
            "no mention of",
        ]
        if any(indicator in llm_response.lower() for indicator in negative_indicators):
            is_answered = False

        top_score = filtered_results[0].similarity_score if filtered_results else 0.0

        final_result = AnswerResult(
            question=question,
            answer=llm_response,
            is_answered=is_answered,
            evidence=evidence_items,
            confidence_score=round(top_score, 4),
            retrieved_chunks_count=len(filtered_results),
            cached=False,
            session_id=session_id,
            document_filter=document_name,
        )

        # Store in cache
        self.cache.set(cache_query_key, final_result.model_dump())

        # Store in session history
        if session_id:
            SessionManager.get_instance().add_message(session_id, "user", clean_query)
            SessionManager.get_instance().add_message(session_id, "assistant", llm_response)

        return final_result

    def list_documents(self) -> List[Dict[str, Any]]:
        return self.vector_store.list_documents()

    def delete_document(self, document_name: str) -> int:
        deleted = self.vector_store.delete_document(document_name)
        if deleted > 0:
            self.cache.invalidate_all()
        return deleted

    def get_stats(self) -> Dict[str, Any]:
        base_stats = self.vector_store.get_stats()
        base_stats["cache"] = self.cache.get_stats()
        return base_stats


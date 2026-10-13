import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from pathlib import Path

from app.config import Settings, get_settings
from app.services.rag_service import RAGService
from app.api.schemas import (
    QueryRequest,
    QueryResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    BatchUploadResponse,
    HealthResponse,
    EvidenceSchema,
    DocumentInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Knowledge Assistant"])

# Dependency provider for RAGService singleton
_rag_service_instance = None


def get_rag_service(settings: Settings = Depends(get_settings)) -> RAGService:
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = RAGService(settings=settings)
    return _rag_service_instance


@router.post(
    "/documents/upload",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest PDF, TXT, or Markdown documents",
)
async def upload_documents(
    files: List[UploadFile] = File(...),
    rag_service: RAGService = Depends(get_rag_service),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files were provided for upload.")

    results: List[DocumentUploadResponse] = []
    errors: List[str] = []

    for file in files:
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower()

        if ext not in {".pdf", ".txt", ".md", ".markdown"}:
            errors.append(f"Skipped '{filename}': Unsupported format '{ext}'. Must be .pdf, .txt, or .md.")
            continue

        try:
            content = await file.read()
            if not content:
                errors.append(f"Skipped '{filename}': File is empty.")
                continue

            result = rag_service.ingest_document(content=content, filename=filename)
            results.append(
                DocumentUploadResponse(
                    filename=result.filename,
                    file_type=result.file_type,
                    total_pages=result.total_pages,
                    chunks_created=result.chunks_created,
                    message=result.message,
                )
            )
        except Exception as e:
            logger.error(f"Failed to ingest file '{filename}': {e}", exc_info=True)
            errors.append(f"Failed to process '{filename}': {str(e)}")

    return BatchUploadResponse(
        results=results,
        successful_count=len(results),
        failed_count=len(errors),
        errors=errors,
    )


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List all indexed documents with chunk and page counts",
)
def list_documents(rag_service: RAGService = Depends(get_rag_service)):
    docs = rag_service.list_documents()
    items = [
        DocumentInfo(
            document_name=d["document_name"],
            chunk_count=d["chunk_count"],
            total_pages=d["total_pages"],
        )
        for d in docs
    ]
    return DocumentListResponse(documents=items, total_documents=len(items))


@router.delete(
    "/documents/{document_name}",
    summary="Delete a document and its embeddings from the vector store",
)
def delete_document(document_name: str, rag_service: RAGService = Depends(get_rag_service)):
    deleted_count = rag_service.delete_document(document_name)
    if deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{document_name}' was not found in the vector store.",
        )
    return {
        "status": "success",
        "message": f"Deleted {deleted_count} chunk(s) for document '{document_name}'.",
        "document_name": document_name,
    }


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Ask questions grounded strictly in the indexed documents",
)
async def query_knowledge_base(
    payload: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    try:
        result = await rag_service.answer_question(question=payload.question)
        evidence = [
            EvidenceSchema(
                document_name=item.document_name,
                page_number=item.page_number,
                chunk_id=item.chunk_id,
                excerpt=item.excerpt,
                similarity_score=item.similarity_score,
            )
            for item in result.evidence
        ]
        return QueryResponse(
            question=result.question,
            answer=result.answer,
            is_answered=result.is_answered,
            evidence=evidence,
            confidence_score=result.confidence_score,
            retrieved_chunks_count=result.retrieved_chunks_count,
            cached=result.cached,
        )
    except Exception as e:
        logger.error(f"Error handling query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def health_check(
    settings: Settings = Depends(get_settings),
    rag_service: RAGService = Depends(get_rag_service),
):
    stats = rag_service.get_stats()
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        model=settings.ollama_model,
        llm_endpoint=settings.chat_completions_url,
        total_indexed_chunks=stats.get("total_chunks", 0),
        total_indexed_documents=stats.get("total_documents", 0),
    )


@router.get("/stats", summary="Get vector store and index statistics")
def get_stats(rag_service: RAGService = Depends(get_rag_service)):
    return rag_service.get_stats()

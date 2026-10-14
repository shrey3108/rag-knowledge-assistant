from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=2,
        description="The question to be answered using the indexed documents.",
        examples=["What are the principles of our AI ethics policy?"]
    )
    document_name: Optional[str] = Field(
        default=None,
        description="Optional: Target search strictly to this specific document."
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional: Conversation session ID for multi-turn conversational context."
    )


class EvidenceSchema(BaseModel):
    document_name: str
    page_number: int
    chunk_id: str
    excerpt: str
    similarity_score: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    is_answered: bool
    evidence: List[EvidenceSchema]
    confidence_score: float
    retrieved_chunks_count: int
    cached: bool = False
    document_filter: Optional[str] = None
    session_id: Optional[str] = None




class DocumentInfo(BaseModel):
    document_name: str
    chunk_count: int
    total_pages: int


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total_documents: int


class DocumentUploadResponse(BaseModel):
    filename: str
    file_type: str
    total_pages: int
    chunks_created: int
    message: str


class BatchUploadResponse(BaseModel):
    results: List[DocumentUploadResponse]
    successful_count: int
    failed_count: int
    errors: List[str] = []


class HealthResponse(BaseModel):
    status: str
    version: str
    model: str
    llm_endpoint: str
    total_indexed_chunks: int
    total_indexed_documents: int

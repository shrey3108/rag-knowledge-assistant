import datetime
import hashlib
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.routes import get_rag_service
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Frontend Compatibility API"])

# In-memory user registry for the React frontend
USERS_DB: Dict[str, Dict[str, Any]] = {}
DOCS_REGISTRY: Dict[str, Dict[str, Any]] = {}
SESSIONS_DB: Dict[str, Dict[str, Any]] = {}
SESSION_MESSAGES_DB: Dict[str, List[Dict[str, Any]]] = {}


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# -------------------------------------------------------------
# Schemas
# -------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserProfileResponse(BaseModel):
    id: str
    username: str
    email: str
    is_active: bool = True
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin_email: str


class SourceChunk(BaseModel):
    chunk_id: str
    content: str
    similarity_score: float


class ChatAskRequest(BaseModel):
    document_id: str
    question: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    document_id: str
    answer: str
    sources: List[SourceChunk]


class ChatMessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ChatSessionItem(BaseModel):
    id: str
    title: Optional[str] = None
    document_id: str
    created_at: str
    updated_at: str


class DocumentUploadResponse(BaseModel):
    message: str
    document_id: str
    filename: str
    file_type: str
    file_size: int
    page_count: Optional[int] = 1
    chunk_count: Optional[int] = 0
    status: str = "ready"


class DocumentItem(BaseModel):
    document_id: str
    filename: str
    file_type: str
    file_size: int
    page_count: Optional[int] = 1
    chunk_count: Optional[int] = 0
    status: str = "ready"
    created_at: str


# -------------------------------------------------------------
# Auth Routes
# -------------------------------------------------------------
@router.post("/auth/register", response_model=UserProfileResponse)
def register_user(req: UserRegisterRequest):
    email = req.email.lower().strip()
    if email in USERS_DB:
        user_info = USERS_DB[email]
        return UserProfileResponse(
            id=user_info["id"],
            username=user_info["username"],
            email=user_info["email"],
            is_active=True,
            created_at=user_info["created_at"],
        )

    user_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    USERS_DB[email] = {
        "id": user_id,
        "username": req.username,
        "email": email,
        "password": hash_pw(req.password),
        "created_at": now,
    }
    return UserProfileResponse(
        id=user_id,
        username=req.username,
        email=email,
        is_active=True,
        created_at=now,
    )


@router.post("/auth/login", response_model=TokenResponse)
def login_user(req: UserLoginRequest):
    email = req.email.lower().strip()
    user_info = USERS_DB.get(email)

    # Auto-register if not yet registered for seamless development
    if not user_info:
        user_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        user_info = {
            "id": user_id,
            "username": email.split("@")[0],
            "email": email,
            "password": hash_pw(req.password),
            "created_at": now,
        }
        USERS_DB[email] = user_info

    token = f"token_{user_info['id'][:8]}_{int(datetime.datetime.now().timestamp())}"
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserProfileResponse(
            id=user_info["id"],
            username=user_info["username"],
            email=user_info["email"],
            is_active=True,
            created_at=user_info["created_at"],
        ),
    )


@router.get("/auth/me", response_model=UserProfileResponse)
def get_current_user():
    # Return first user or default active profile
    if USERS_DB:
        user_info = next(iter(USERS_DB.values()))
    else:
        user_info = {
            "id": str(uuid.uuid4()),
            "username": "shrey",
            "email": "shreyshukla318@gmail.com",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    return UserProfileResponse(
        id=user_info["id"],
        username=user_info["username"],
        email=user_info["email"],
        is_active=True,
        created_at=user_info["created_at"],
    )


@router.post("/admin/login", response_model=AdminLoginResponse)
def admin_login(req: AdminLoginRequest):
    token = f"admin_token_{int(datetime.datetime.now().timestamp())}"
    return AdminLoginResponse(access_token=token, admin_email=req.email)


# -------------------------------------------------------------
# Documents Routes (React Frontend compatibility)
# -------------------------------------------------------------
@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document_frontend(
    file: UploadFile = File(...),
    rag_service: RAGService = Depends(get_rag_service),
):
    filename = file.filename or "uploaded_document.pdf"
    content = await file.read()
    file_size = len(content)

    # Ingest document through standard RAG Service
    result = rag_service.ingest_document(filename=filename, content=content)

    # Find existing or assign new UUID for this document
    doc_id = None
    for did, dinfo in DOCS_REGISTRY.items():
        if dinfo["filename"] == filename:
            doc_id = did
            break
    if not doc_id:
        doc_id = str(uuid.uuid4())

    DOCS_REGISTRY[doc_id] = {
        "document_id": doc_id,
        "filename": filename,
        "file_type": result.file_type,
        "file_size": file_size,
        "page_count": result.total_pages,
        "chunk_count": result.chunks_created,
        "status": "ready",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    return DocumentUploadResponse(
        message=result.message,
        document_id=doc_id,
        filename=filename,
        file_type=result.file_type,
        file_size=file_size,
        page_count=result.total_pages,
        chunk_count=result.chunks_created,
        status="ready",
    )


@router.get("/documents/", response_model=List[DocumentItem])
def list_documents_frontend(rag_service: RAGService = Depends(get_rag_service)):
    # Sync with ChromaDB indexed documents
    indexed_docs = rag_service.vector_store.list_documents()
    for d in indexed_docs:
        fname = d["document_name"]
        # Ensure registered
        found = False
        for dinfo in DOCS_REGISTRY.values():
            if dinfo["filename"] == fname:
                found = True
                break
        if not found:
            doc_id = str(uuid.uuid4())
            DOCS_REGISTRY[doc_id] = {
                "document_id": doc_id,
                "filename": fname,
                "file_type": fname.split(".")[-1] if "." in fname else "txt",
                "file_size": 1024 * d.get("chunk_count", 1),
                "page_count": d.get("total_pages", 1),
                "chunk_count": d.get("chunk_count", 1),
                "status": "ready",
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

    return [DocumentItem(**d) for d in DOCS_REGISTRY.values()]


@router.delete("/documents/{document_id}")
def delete_document_frontend(
    document_id: str,
    rag_service: RAGService = Depends(get_rag_service),
):
    doc_info = DOCS_REGISTRY.pop(document_id, None)
    if doc_info:
        rag_service.vector_store.delete_document(doc_info["filename"])
    else:
        rag_service.vector_store.delete_document(document_id)
    return {"status": "success"}


# -------------------------------------------------------------
# Chat Routes (React Frontend compatibility)
# -------------------------------------------------------------
@router.post("/chat/ask", response_model=ChatResponse)
async def ask_chat(
    req: ChatAskRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    # Ensure valid UUID session_id for React router validation
    session_id = req.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
    else:
        try:
            uuid.UUID(session_id)
        except ValueError:
            session_id = str(uuid.uuid4())

    # Map document_id to filename if needed
    doc_info = DOCS_REGISTRY.get(req.document_id)
    filter_filename = doc_info["filename"] if doc_info else req.document_id

    # Query RAG service with Ollama Cloud 120B model
    result = await rag_service.query(
        question=req.question,
        session_id=session_id,
        document_name=filter_filename if filter_filename else None,
    )

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Track session metadata
    if session_id not in SESSIONS_DB:
        title = req.question[:40] + ("..." if len(req.question) > 40 else "")
        SESSIONS_DB[session_id] = {
            "id": session_id,
            "title": title,
            "document_id": req.document_id,
            "created_at": now,
            "updated_at": now,
        }
    else:
        SESSIONS_DB[session_id]["updated_at"] = now

    # Store messages for React chat loader
    if session_id not in SESSION_MESSAGES_DB:
        SESSION_MESSAGES_DB[session_id] = []

    user_msg_id = str(uuid.uuid4())
    ai_msg_id = str(uuid.uuid4())

    SESSION_MESSAGES_DB[session_id].append(
        {"id": user_msg_id, "role": "user", "content": req.question, "created_at": now}
    )
    SESSION_MESSAGES_DB[session_id].append(
        {"id": ai_msg_id, "role": "assistant", "content": result.answer, "created_at": now}
    )

    sources = [
        SourceChunk(
            chunk_id=item.chunk_id,
            content=item.excerpt,
            similarity_score=item.similarity_score,
        )
        for item in result.evidence
    ]

    return ChatResponse(
        session_id=session_id,
        message_id=ai_msg_id,
        document_id=req.document_id,
        answer=result.answer,
        sources=sources,
    )


@router.get("/chat/sessions", response_model=List[ChatSessionItem])
def list_chat_sessions():
    return [ChatSessionItem(**s) for s in SESSIONS_DB.values()]


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionItem)
def get_chat_session(session_id: str):
    session = SESSIONS_DB.get(session_id)
    if not session:
        # Create on the fly so loader doesn't fail
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        session = {
            "id": session_id,
            "title": "Chat Session",
            "document_id": "default",
            "created_at": now,
            "updated_at": now,
        }
        SESSIONS_DB[session_id] = session
    return ChatSessionItem(**session)


@router.get("/chat/sessions/{session_id}/messages", response_model=List[ChatMessageItem])
def get_chat_messages(session_id: str):
    msgs = SESSION_MESSAGES_DB.get(session_id, [])
    return [ChatMessageItem(**m) for m in msgs]


@router.delete("/chat/sessions/{session_id}")
def delete_chat_session(session_id: str):
    SESSIONS_DB.pop(session_id, None)
    SESSION_MESSAGES_DB.pop(session_id, None)
    return {"status": "deleted"}

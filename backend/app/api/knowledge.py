from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole
from backend.app.schemas.knowledge import (
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResponse,
)
from backend.app.services.knowledge_service import (
    create_and_ingest_document,
    delete_knowledge_document,
    get_knowledge_document,
    list_knowledge_documents,
)
from backend.app.services.retrieval_service import retrieve_relevant_chunks

router = APIRouter(
    prefix="/api/v1/company/knowledge",
    tags=["Company Knowledge & RAG"],
)

MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB limit


def _build_doc_response(doc) -> KnowledgeDocumentResponse:
    chunk_count = len(doc.chunks) if doc.chunks else 0
    return KnowledgeDocumentResponse(
        id=doc.id,
        company_id=doc.company_id,
        title=doc.title,
        original_filename=doc.original_filename,
        content_type=doc.content_type,
        description=doc.description,
        status=doc.status,
        processing_error=doc.processing_error,
        chunk_count=chunk_count,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post(
    "/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest reference document",
)
async def upload_knowledge_document(
    file: UploadFile = File(..., description="Document file (PDF, DOCX, TXT)"),
    title: Optional[str] = Form(None, description="Optional custom title for the document"),
    description: Optional[str] = Form(None, description="Optional document description"),
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Upload and synchronously ingest a company knowledge document:
    - Extracts text from PDF, DOCX, or TXT.
    - Deterministically chunks text with overlap.
    - Generates 384-dimensional dense vector embeddings.
    - Persists chunks and embeddings in pgvector under tenant isolation.
    """
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    try:
        doc = create_and_ingest_document(
            db=db,
            company_id=current_user.company_id,
            filename=file.filename or "uploaded_document",
            file_bytes=file_bytes,
            content_type=file.content_type or "application/octet-stream",
            title=title,
            description=description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _build_doc_response(doc)


@router.get(
    "/documents",
    response_model=KnowledgeDocumentListResponse,
    summary="List company knowledge documents",
)
def list_company_documents(
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
            UserRole.REVIEWER,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve all knowledge documents for the authenticated company.
    """
    docs = list_knowledge_documents(db=db, company_id=current_user.company_id)
    doc_responses = [_build_doc_response(d) for d in docs]
    return KnowledgeDocumentListResponse(
        total=len(doc_responses),
        documents=doc_responses,
    )


@router.get(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentResponse,
    summary="Get knowledge document metadata",
)
def get_document_details(
    document_id: int,
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
            UserRole.REVIEWER,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve metadata, processing status, and chunk count for a specific document.
    Enforces tenant isolation.
    """
    doc = get_knowledge_document(
        db=db,
        company_id=current_user.company_id,
        document_id=document_id,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge document {document_id} not found for this company.",
        )
    return _build_doc_response(doc)


@router.delete(
    "/documents/{document_id}",
    summary="Delete a knowledge document",
)
def delete_document(
    document_id: int,
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Delete a knowledge document and all its associated chunks and embeddings.
    Restricted to Company Admin and Editor roles (Reviewer gets 403).
    """
    success = delete_knowledge_document(
        db=db,
        company_id=current_user.company_id,
        document_id=document_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge document {document_id} not found for this company.",
        )
    return {"message": "Knowledge document deleted successfully", "id": document_id}


@router.post(
    "/retrieve",
    response_model=KnowledgeRetrievalResponse,
    summary="Retrieve relevant knowledge chunks (RAG)",
)
def retrieve_knowledge(
    payload: KnowledgeRetrievalRequest,
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
            UserRole.REVIEWER,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Semantic retrieval over company knowledge base.
    Uses pgvector cosine distance filtered strictly by current_user.company_id.
    """
    results = retrieve_relevant_chunks(
        db=db,
        company_id=current_user.company_id,
        query=payload.query,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
    )
    return KnowledgeRetrievalResponse(
        query=payload.query,
        total_results=len(results),
        results=results,
    )

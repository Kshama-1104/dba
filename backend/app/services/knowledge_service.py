import os
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.models.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeEmbedding,
)
from backend.app.services.chunking_service import ChunkingService
from backend.app.services.embedding_service import get_embedding_provider
from backend.app.services.text_extraction_service import TextExtractionService


def create_and_ingest_document(
    db: Session,
    company_id: int,
    filename: str,
    file_bytes: bytes,
    content_type: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> KnowledgeDocument:
    """
    Ingest a new company reference document:
    1. Register document in database with status UPLOADED.
    2. Extract normalized text (PDF, DOCX, TXT).
    3. Recursively chunk text.
    4. Generate 384-dimensional embeddings.
    5. Persist chunks and vector embeddings.
    6. Transition status to READY.
    
    If extraction or embedding fails, transitions status to FAILED with error details.
    Enforces strict tenant isolation by binding all records to company_id.
    """
    doc_title = title.strip() if title and title.strip() else filename
    safe_file_url = f"uploads/company_{company_id}/{uuid.uuid4().hex}_{os.path.basename(filename)}"

    # Step 1: Create initial document record
    document = KnowledgeDocument(
        company_id=company_id,
        title=doc_title,
        original_filename=os.path.basename(filename),
        file_url=safe_file_url,
        content_type=content_type or "application/octet-stream",
        description=description,
        status=KnowledgeDocumentStatus.UPLOADED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        # Step 2: Extraction
        document.status = KnowledgeDocumentStatus.PROCESSING
        db.commit()

        extracted_text = TextExtractionService.extract_text(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
        )

        # Step 3: Chunking
        chunker = ChunkingService()
        chunks_data = chunker.chunk_text(extracted_text)
        if not chunks_data:
            raise ValueError("Document yielded zero usable text chunks after extraction.")

        # Step 4: Embedding generation
        embedding_provider = get_embedding_provider()
        chunk_texts = [c.content for c in chunks_data]
        vectors = embedding_provider.embed_texts(chunk_texts)

        # Step 5: Persist chunks and embeddings atomically
        for chunk_meta, vector in zip(chunks_data, vectors):
            chunk = KnowledgeChunk(
                company_id=company_id,
                document_id=document.id,
                chunk_index=chunk_meta.chunk_index,
                content=chunk_meta.content,
                token_count=chunk_meta.token_count,
                created_at=datetime.utcnow(),
            )
            db.add(chunk)
            db.flush()  # populate chunk.id

            emb = KnowledgeEmbedding(
                company_id=company_id,
                chunk_id=chunk.id,
                embedding_model=embedding_provider.model_name,
                embedding=vector,
                created_at=datetime.utcnow(),
            )
            db.add(emb)

        # Step 6: Transition status to READY
        document.status = KnowledgeDocumentStatus.READY
        document.processing_error = None
        document.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(document)
        return document

    except Exception as exc:
        db.rollback()
        # Mark document as FAILED with error reason
        doc_failed = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id == document.id,
            KnowledgeDocument.company_id == company_id,
        ).first()
        if doc_failed:
            doc_failed.status = KnowledgeDocumentStatus.FAILED
            doc_failed.processing_error = str(exc)
            doc_failed.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(doc_failed)
            document = doc_failed
        raise ValueError(f"Document ingestion failed: {str(exc)}") from exc


def get_knowledge_document(
    db: Session,
    company_id: int,
    document_id: int,
) -> Optional[KnowledgeDocument]:
    """
    Retrieve document by ID with strict tenant isolation.
    """
    return (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.company_id == company_id,
        )
        .first()
    )


def list_knowledge_documents(
    db: Session,
    company_id: int,
) -> List[KnowledgeDocument]:
    """
    List all knowledge documents belonging to the company.
    """
    return (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.company_id == company_id)
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )


def delete_knowledge_document(
    db: Session,
    company_id: int,
    document_id: int,
) -> bool:
    """
    Delete a knowledge document and its associated chunks/embeddings.
    Enforces strict tenant isolation.
    """
    doc = get_knowledge_document(db=db, company_id=company_id, document_id=document_id)
    if not doc:
        return False

    db.delete(doc)
    db.commit()
    return True

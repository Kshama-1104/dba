import pytest
from sqlalchemy.orm import Session

from backend.app.models.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeEmbedding,
)
from backend.app.services.knowledge_service import (
    create_and_ingest_document,
    delete_knowledge_document,
    get_knowledge_document,
    list_knowledge_documents,
)
from backend.tests.test_text_extraction import create_sample_docx, create_sample_pdf


def test_ingest_txt_document_success(db_session: Session, create_company):
    company = create_company()
    content = "DailyBlog AI reference guidelines.\n\nAll content must maintain an authoritative tone."
    file_bytes = content.encode("utf-8")

    doc = create_and_ingest_document(
        db=db_session,
        company_id=company.id,
        filename="guidelines.txt",
        file_bytes=file_bytes,
        content_type="text/plain",
        title="Brand Guidelines",
        description="Core company guidelines for blog generation",
    )

    assert doc.id is not None
    assert doc.company_id == company.id
    assert doc.title == "Brand Guidelines"
    assert doc.status == KnowledgeDocumentStatus.READY
    assert doc.processing_error is None

    # Verify chunks persisted in DB
    chunks = db_session.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).all()
    assert len(chunks) > 0
    assert chunks[0].company_id == company.id

    # Verify embeddings persisted in DB with 384 dimensions
    for chunk in chunks:
        emb = db_session.query(KnowledgeEmbedding).filter(KnowledgeEmbedding.chunk_id == chunk.id).first()
        assert emb is not None
        assert emb.company_id == company.id
        assert len(emb.embedding) == 384


def test_ingest_pdf_document_success(db_session: Session, create_company):
    company = create_company()
    pdf_bytes = create_sample_pdf("Enterprise Cloud Architecture Whitepaper")

    doc = create_and_ingest_document(
        db=db_session,
        company_id=company.id,
        filename="architecture.pdf",
        file_bytes=pdf_bytes,
        content_type="application/pdf",
    )

    assert doc.status == KnowledgeDocumentStatus.READY
    assert doc.title == "architecture.pdf"

    chunks = db_session.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).all()
    assert len(chunks) > 0


def test_ingest_docx_document_success(db_session: Session, create_company):
    company = create_company()
    docx_bytes = create_sample_docx("Quarterly product catalog and customer review data.")

    doc = create_and_ingest_document(
        db=db_session,
        company_id=company.id,
        filename="catalog.docx",
        file_bytes=docx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        title="Product Catalog",
    )

    assert doc.status == KnowledgeDocumentStatus.READY
    chunks = db_session.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).all()
    assert len(chunks) > 0


def test_ingest_empty_document_records_failed_status(db_session: Session, create_company):
    company = create_company()

    with pytest.raises(ValueError, match="empty"):
        create_and_ingest_document(
            db=db_session,
            company_id=company.id,
            filename="empty.txt",
            file_bytes=b"",
            content_type="text/plain",
        )

    # Document record in DB reflects FAILED status and records processing_error
    doc = (
        db_session.query(KnowledgeDocument)
        .filter(KnowledgeDocument.company_id == company.id, KnowledgeDocument.original_filename == "empty.txt")
        .first()
    )
    assert doc is not None
    assert doc.status == KnowledgeDocumentStatus.FAILED
    assert doc.processing_error is not None
    assert "empty" in doc.processing_error.lower()


def test_tenant_isolation_in_knowledge_service(db_session: Session, create_company):
    company_a = create_company(name="Company A")
    company_b = create_company(name="Company B")

    doc_a = create_and_ingest_document(
        db=db_session,
        company_id=company_a.id,
        filename="secret_a.txt",
        file_bytes=b"Company A confidential roadmaps.",
        content_type="text/plain",
    )

    # Company A can access its document
    assert get_knowledge_document(db=db_session, company_id=company_a.id, document_id=doc_a.id) is not None

    # Company B CANNOT access Company A's document
    assert get_knowledge_document(db=db_session, company_id=company_b.id, document_id=doc_a.id) is None

    # list_knowledge_documents only returns company's own documents
    docs_b = list_knowledge_documents(db=db_session, company_id=company_b.id)
    assert len(docs_b) == 0


def test_delete_knowledge_document_cascades(db_session: Session, create_company):
    company = create_company()
    doc = create_and_ingest_document(
        db=db_session,
        company_id=company.id,
        filename="doc_to_delete.txt",
        file_bytes=b"Content to be deleted.",
        content_type="text/plain",
    )

    doc_id = doc.id
    chunks = db_session.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc_id).all()
    assert len(chunks) > 0
    chunk_id = chunks[0].id

    # Delete document
    deleted = delete_knowledge_document(db=db_session, company_id=company.id, document_id=doc_id)
    assert deleted is True

    # Document is gone
    assert get_knowledge_document(db=db_session, company_id=company.id, document_id=doc_id) is None
    # Chunks are gone
    assert db_session.query(KnowledgeChunk).filter(KnowledgeChunk.id == chunk_id).first() is None
    # Embeddings are gone
    assert db_session.query(KnowledgeEmbedding).filter(KnowledgeEmbedding.chunk_id == chunk_id).first() is None


def test_atomic_rollback_on_embedding_failure(db_session: Session, create_company, monkeypatch):
    """
    Verify atomic rollback:
    When embedding generation fails midway, the database MUST NOT retain orphan chunks or embeddings.
    The document record transitions to FAILED with the error reason recorded.
    """
    from backend.app.services import embedding_service
    from backend.app.services.embedding_service import EmbeddingProvider

    class FailingEmbeddingProvider(EmbeddingProvider):
        @property
        def dimension(self) -> int:
            return 384

        @property
        def model_name(self) -> str:
            return "failing-model"

        def embed_text(self, text: str):
            raise RuntimeError("Simulated embedding infrastructure outage")

        def embed_texts(self, texts):
            raise RuntimeError("Simulated embedding infrastructure outage")

    monkeypatch.setattr(embedding_service, "_default_provider", FailingEmbeddingProvider())

    company = create_company()
    with pytest.raises(ValueError, match="Simulated embedding infrastructure outage"):
        create_and_ingest_document(
            db=db_session,
            company_id=company.id,
            filename="crash_test.txt",
            file_bytes=b"This text will fail during embedding generation.",
            content_type="text/plain",
        )

    # Document should be marked FAILED
    doc = (
        db_session.query(KnowledgeDocument)
        .filter(KnowledgeDocument.company_id == company.id, KnowledgeDocument.original_filename == "crash_test.txt")
        .first()
    )
    assert doc is not None
    assert doc.status == KnowledgeDocumentStatus.FAILED
    assert "Simulated embedding infrastructure outage" in doc.processing_error

    # ZERO chunks must exist in DB for this document
    chunks = db_session.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).all()
    assert len(chunks) == 0

    # ZERO embeddings must exist in DB for this document
    embs = db_session.query(KnowledgeEmbedding).filter(KnowledgeEmbedding.company_id == company.id).all()
    assert len(embs) == 0


from sqlalchemy.orm import Session

from backend.app.services.knowledge_service import create_and_ingest_document
from backend.app.services.retrieval_service import retrieve_relevant_chunks


def test_retrieval_semantic_ranking(db_session: Session, create_company):
    company = create_company()

    doc = create_and_ingest_document(
        db=db_session,
        company_id=company.id,
        filename="ai_guide.txt",
        file_bytes=(
            "Artificial intelligence machine learning deep learning neural networks algorithms.\n\n"
            "Culinary recipes for baking bread with yeast, flour, water, and salt.\n\n"
            "Automotive repair, internal combustion engines, transmissions, and brake pads."
        ).encode("utf-8"),
        content_type="text/plain",
        title="AI and Technology Guide",
    )

    # Search for AI topic
    results = retrieve_relevant_chunks(
        db=db_session,
        company_id=company.id,
        query="machine learning neural networks",
        top_k=2,
    )

    assert len(results) > 0
    # Top result should be the AI chunk
    top_chunk = results[0]
    assert "neural networks" in top_chunk.content.lower()
    assert top_chunk.document_id == doc.id
    assert top_chunk.document_title == "AI and Technology Guide"
    assert top_chunk.similarity_score > 0.0


def test_retrieval_strict_tenant_isolation(db_session: Session, create_company):
    """
    CRITICAL ARCHITECTURAL INVARIANT:
    Company A retrieval MUST NOT return Company B knowledge under any operational condition.
    """
    company_a = create_company(name="Company A")
    company_b = create_company(name="Company B")

    # Both companies ingest documents with the exact same keywords
    create_and_ingest_document(
        db=db_session,
        company_id=company_a.id,
        filename="company_a_strategy.txt",
        file_bytes=b"Quantum computing encryption algorithms developed by Company Alpha.",
        content_type="text/plain",
        title="Alpha Strategy",
    )

    create_and_ingest_document(
        db=db_session,
        company_id=company_b.id,
        filename="company_b_strategy.txt",
        file_bytes=b"Quantum computing encryption algorithms developed by Company Beta.",
        content_type="text/plain",
        title="Beta Strategy",
    )

    # Company A searches for quantum computing
    results_a = retrieve_relevant_chunks(
        db=db_session,
        company_id=company_a.id,
        query="Quantum computing encryption algorithms",
        top_k=10,
    )

    # Every single returned chunk MUST belong to Company A
    assert len(results_a) > 0
    for chunk in results_a:
        assert chunk.document_title == "Alpha Strategy"
        assert "Alpha" in chunk.content
        assert "Beta" not in chunk.content

    # Company B searches for quantum computing
    results_b = retrieve_relevant_chunks(
        db=db_session,
        company_id=company_b.id,
        query="Quantum computing encryption algorithms",
        top_k=10,
    )

    assert len(results_b) > 0
    for chunk in results_b:
        assert chunk.document_title == "Beta Strategy"
        assert "Beta" in chunk.content
        assert "Alpha" not in chunk.content


def test_retrieval_top_k_and_filtering(db_session: Session, create_company):
    company = create_company()

    doc1 = create_and_ingest_document(
        db=db_session,
        company_id=company.id,
        filename="doc1.txt",
        file_bytes=b"Chapter 1 on cloud infrastructure.\n\nChapter 2 on containerization.\n\nChapter 3 on serverless.",
        content_type="text/plain",
        title="Doc 1",
    )
    doc2 = create_and_ingest_document(
        db=db_session,
        company_id=company.id,
        filename="doc2.txt",
        file_bytes=b"Specialized networking manual for cloud VPCs and firewalls.",
        content_type="text/plain",
        title="Doc 2",
    )

    # Top-k = 1
    res_k1 = retrieve_relevant_chunks(
        db=db_session,
        company_id=company.id,
        query="cloud infrastructure networking",
        top_k=1,
    )
    assert len(res_k1) == 1

    # Filter by specific document
    res_filter = retrieve_relevant_chunks(
        db=db_session,
        company_id=company.id,
        query="cloud",
        top_k=10,
        document_ids=[doc2.id],
    )
    for r in res_filter:
        assert r.document_id == doc2.id


def test_retrieval_empty_query_or_unknown_company(db_session: Session, create_company):
    company = create_company()
    create_and_ingest_document(
        db=db_session,
        company_id=company.id,
        filename="data.txt",
        file_bytes=b"Some test data for retrieval.",
        content_type="text/plain",
    )

    # Empty query
    assert retrieve_relevant_chunks(db=db_session, company_id=company.id, query="") == []
    assert retrieve_relevant_chunks(db=db_session, company_id=company.id, query="   ") == []

    # Nonexistent company ID
    assert retrieve_relevant_chunks(db=db_session, company_id=999999, query="test data") == []


def test_retrieval_excludes_failed_and_archived_documents(db_session: Session, create_company):
    from backend.app.models.knowledge import KnowledgeDocument, KnowledgeDocumentStatus

    company = create_company()
    doc_ready = create_and_ingest_document(
        db=db_session,
        company_id=company.id,
        filename="ready_doc.txt",
        file_bytes=b"Active knowledge in ready status.",
        content_type="text/plain",
        title="Ready Document",
    )
    doc_archived = create_and_ingest_document(
        db=db_session,
        company_id=company.id,
        filename="archived_doc.txt",
        file_bytes=b"Old knowledge that is now archived.",
        content_type="text/plain",
        title="Archived Document",
    )

    # Manually transition doc_archived to ARCHIVED status
    doc_to_archive = db_session.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_archived.id).first()
    doc_to_archive.status = KnowledgeDocumentStatus.ARCHIVED
    db_session.commit()

    # Search for "knowledge"
    results = retrieve_relevant_chunks(
        db=db_session,
        company_id=company.id,
        query="knowledge",
        top_k=10,
    )

    # Only the READY document should be retrieved
    assert len(results) > 0
    for r in results:
        assert r.document_id == doc_ready.id
        assert r.document_title == "Ready Document"
        assert r.document_id != doc_archived.id


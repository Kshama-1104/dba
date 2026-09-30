import pytest
from sqlalchemy.orm import Session

from backend.app.models.company_ai_profile import CompanyAIProfile
from backend.app.models.company_memory import (
    CompanyMemory,
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from backend.app.schemas.company_memory import CompanyMemoryCreate, CompanyMemoryUpdate
from backend.app.services.memory_service import (
    create_company_memory,
    delete_company_memory,
    get_company_memory,
    list_company_memories,
    resolve_profile_memory_conflicts,
    retrieve_relevant_memories,
    supersede_company_memory,
    update_company_memory,
)


def test_create_semantic_memory_with_embedding(db_session: Session, create_company):
    company = create_company()
    mem_in = CompanyMemoryCreate(
        memory_type=MemoryType.SEMANTIC,
        content="NexaCore provides automated AI content distribution for commercial logistics.",
        source=MemorySource.COMPANY_PROFILE,
        confidence=MemoryConfidence.HIGH,
        importance=5,
    )

    mem = create_company_memory(db=db_session, company_id=company.id, memory_in=mem_in)
    assert mem.id is not None
    assert mem.company_id == company.id
    assert mem.memory_type == MemoryType.SEMANTIC
    assert mem.status == MemoryStatus.ACTIVE
    assert mem.embedding is not None
    assert len(mem.embedding) == 384


def test_create_episodic_memory(db_session: Session, create_company):
    company = create_company()
    mem_in = CompanyMemoryCreate(
        memory_type=MemoryType.EPISODIC,
        content="In September 2026, the Editor rejected topic 'Crypto Micro-transactions' as off-brand.",
        source=MemorySource.EDITOR_CHAT,
        confidence=MemoryConfidence.HIGH,
        importance=4,
    )

    mem = create_company_memory(db=db_session, company_id=company.id, memory_in=mem_in)
    assert mem.memory_type == MemoryType.EPISODIC
    assert mem.source == MemorySource.EDITOR_CHAT


def test_create_procedural_memory(db_session: Session, create_company):
    company = create_company()
    mem_in = CompanyMemoryCreate(
        memory_type=MemoryType.PROCEDURAL,
        content="Always structure product introductions with a problem hook before the thesis.",
        source=MemorySource.REVIEWER_FEEDBACK,
        confidence=MemoryConfidence.MEDIUM,
        importance=3,
    )

    mem = create_company_memory(db=db_session, company_id=company.id, memory_in=mem_in)
    assert mem.memory_type == MemoryType.PROCEDURAL
    assert mem.confidence == MemoryConfidence.MEDIUM


def test_sensitive_data_rejection(db_session: Session, create_company):
    company = create_company()

    sensitive_samples = [
        "User password: SuperSecretPassword123!",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token",
        "api_key: sk-1234567890abcdef1234567890abcdef",
        "AWS secret_key: abcdef1234567890",
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...",
    ]

    for sample in sensitive_samples:
        with pytest.raises(ValueError, match="sensitive credentials"):
            CompanyMemoryCreate(
                memory_type=MemoryType.SEMANTIC,
                content=sample,
            )


def test_memory_tenant_isolation_get_and_list(db_session: Session, create_company):
    company_a = create_company(name="Company A")
    company_b = create_company(name="Company B")

    mem_a = create_company_memory(
        db=db_session,
        company_id=company_a.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.SEMANTIC,
            content="Confidential business positioning of Company Alpha.",
        ),
    )

    # Company A can access its memory
    assert get_company_memory(db=db_session, company_id=company_a.id, memory_id=mem_a.id) is not None

    # Company B CANNOT access Company A's memory
    assert get_company_memory(db=db_session, company_id=company_b.id, memory_id=mem_a.id) is None

    # list_company_memories only returns company's memories
    list_b = list_company_memories(db=db_session, company_id=company_b.id)
    assert len(list_b) == 0


def test_memory_lifecycle_status_transitions(db_session: Session, create_company):
    company = create_company()

    # 1. Create as CANDIDATE
    mem = create_company_memory(
        db=db_session,
        company_id=company.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.PROCEDURAL,
            content="Candidate preference extracted from chat conversation.",
            status=MemoryStatus.CANDIDATE,
        ),
    )
    assert mem.status == MemoryStatus.CANDIDATE

    # 2. Transition to ACTIVE
    updated = update_company_memory(
        db=db_session,
        company_id=company.id,
        memory_id=mem.id,
        update_in=CompanyMemoryUpdate(status=MemoryStatus.ACTIVE),
    )
    assert updated.status == MemoryStatus.ACTIVE

    # 3. Transition to ARCHIVED
    delete_company_memory(db=db_session, company_id=company.id, memory_id=mem.id, hard_delete=False)
    archived = get_company_memory(db=db_session, company_id=company.id, memory_id=mem.id)
    assert archived.status == MemoryStatus.ARCHIVED


def test_memory_supersession_preserves_history(db_session: Session, create_company):
    company = create_company()

    # Old memory
    old_mem = create_company_memory(
        db=db_session,
        company_id=company.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.PROCEDURAL,
            content="Preferred call to action: 'Contact our sales team for enterprise pricing.'",
            status=MemoryStatus.ACTIVE,
        ),
    )

    # Superseding new memory
    new_in = CompanyMemoryCreate(
        memory_type=MemoryType.PROCEDURAL,
        content="Preferred call to action: 'Book a 15-minute live platform demonstration.'",
        status=MemoryStatus.ACTIVE,
    )

    new_mem, updated_old_mem = supersede_company_memory(
        db=db_session,
        company_id=company.id,
        old_memory_id=old_mem.id,
        new_memory_in=new_in,
    )

    assert new_mem.status == MemoryStatus.ACTIVE
    assert updated_old_mem.status == MemoryStatus.SUPERSEDED
    assert updated_old_mem.superseded_by_id == new_mem.id

    # Active listing excludes superseded memory by default
    active_mems = list_company_memories(db=db_session, company_id=company.id, active_only=True)
    assert len(active_mems) == 1
    assert active_mems[0].id == new_mem.id


def test_memory_semantic_retrieval_and_tenant_isolation(db_session: Session, create_company):
    company_a = create_company(name="Company A")
    company_b = create_company(name="Company B")

    # Ingest memories for both companies
    create_company_memory(
        db=db_session,
        company_id=company_a.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.SEMANTIC,
            content="Alpha Corp specialized target audience is enterprise cloud engineers.",
        ),
    )
    create_company_memory(
        db=db_session,
        company_id=company_b.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.SEMANTIC,
            content="Beta Corp specialized target audience is enterprise cloud engineers.",
        ),
    )

    # Company A retrieves
    results_a = retrieve_relevant_memories(
        db=db_session,
        company_id=company_a.id,
        query="target audience enterprise cloud engineers",
        top_k=5,
    )

    assert len(results_a) > 0
    for item in results_a:
        assert item.company_id == company_a.id
        assert "Alpha Corp" in item.content
        assert "Beta Corp" not in item.content


def test_memory_retrieval_excludes_superseded_and_archived(db_session: Session, create_company):
    company = create_company()

    # Active memory
    mem_active = create_company_memory(
        db=db_session,
        company_id=company.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.SEMANTIC,
            content="Current active guideline on microservice architecture.",
            status=MemoryStatus.ACTIVE,
        ),
    )
    # Archived memory
    create_company_memory(
        db=db_session,
        company_id=company.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.SEMANTIC,
            content="Old archived guideline on microservice architecture.",
            status=MemoryStatus.ARCHIVED,
        ),
    )

    results = retrieve_relevant_memories(
        db=db_session,
        company_id=company.id,
        query="microservice architecture guideline",
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].id == mem_active.id


def test_memory_conflict_resolution_structured_profile_precedence(db_session: Session, create_company):
    company = create_company()

    # Structured profile specifies Voice: Authoritative
    profile = CompanyAIProfile(
        company_id=company.id,
        brand_voice="Authoritative",
    )
    db_session.add(profile)
    db_session.commit()

    # Contradicting procedural memory recorded previously
    contradicting_mem = create_company_memory(
        db=db_session,
        company_id=company.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.PROCEDURAL,
            content="Preferred brand tone: Witty, playful, and irreverent.",
            source=MemorySource.EDITOR_CHAT,
            status=MemoryStatus.ACTIVE,
        ),
    )

    # Run conflict resolution
    res = resolve_profile_memory_conflicts(db=db_session, company_id=company.id)

    assert res.conflicts_detected == 1
    assert res.structured_profile_precedence_applied is True

    # Contradicting memory is superseded by authoritative profile
    db_session.refresh(contradicting_mem)
    assert contradicting_mem.status == MemoryStatus.SUPERSEDED

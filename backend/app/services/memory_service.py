"""
LONG-TERM COMPANY MEMORY SERVICE

Implements durable semantic, episodic, and procedural memory for enterprise tenants.
Enforces dual-tier separation from short-term thread memory, non-pollution gates,
sensitive-data rejection, supersession auditing, pgvector semantic retrieval,
and strict precedence of structured Company AI Profile over memory.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.app.models.company_ai_profile import CompanyAIProfile
from backend.app.models.company_memory import (
    CompanyMemory,
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from backend.app.schemas.company_memory import (
    CompanyMemoryCreate,
    CompanyMemoryUpdate,
    MemoryConflictResolutionResponse,
    RetrievedMemoryItem,
    validate_no_sensitive_data,
)
from backend.app.services.embedding_service import get_embedding_provider


def create_company_memory(
    db: Session,
    company_id: int,
    memory_in: CompanyMemoryCreate,
    user_id: Optional[int] = None,
) -> CompanyMemory:
    """
    Create and persist a new durable memory item.
    Enforces sensitive data validation and computes pgvector dense embedding.
    """
    # Sensitive data guard
    validate_no_sensitive_data(memory_in.content)

    # Compute dense 384-dimensional vector embedding for semantic search
    provider = get_embedding_provider()
    embedding_vector = provider.embed_text(memory_in.content)

    memory = CompanyMemory(
        company_id=company_id,
        memory_type=memory_in.memory_type,
        content=memory_in.content.strip(),
        source=memory_in.source,
        confidence=memory_in.confidence,
        importance=memory_in.importance,
        status=memory_in.status,
        embedding=embedding_vector,
        created_by_user_id=user_id,
        metadata_payload=memory_in.metadata_payload,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def get_company_memory(
    db: Session,
    company_id: int,
    memory_id: int,
    update_access_time: bool = True,
) -> Optional[CompanyMemory]:
    """
    Retrieve a specific memory by ID with strict tenant isolation.
    """
    memory = (
        db.query(CompanyMemory)
        .filter(
            CompanyMemory.id == memory_id,
            CompanyMemory.company_id == company_id,
        )
        .first()
    )
    if memory and update_access_time:
        memory.last_accessed_at = datetime.utcnow()
        db.commit()
        db.refresh(memory)
    return memory


def list_company_memories(
    db: Session,
    company_id: int,
    memory_type: Optional[MemoryType] = None,
    status: Optional[MemoryStatus] = None,
    active_only: bool = False,
) -> List[CompanyMemory]:
    """
    List memories for the authenticated company with optional filtering.
    """
    query = db.query(CompanyMemory).filter(CompanyMemory.company_id == company_id)

    if memory_type:
        query = query.filter(CompanyMemory.memory_type == memory_type)

    if status:
        query = query.filter(CompanyMemory.status == status)
    elif active_only:
        query = query.filter(CompanyMemory.status == MemoryStatus.ACTIVE)

    return (
        query.order_by(
            CompanyMemory.importance.desc(),
            CompanyMemory.created_at.desc(),
        )
        .all()
    )


def update_company_memory(
    db: Session,
    company_id: int,
    memory_id: int,
    update_in: CompanyMemoryUpdate,
) -> Optional[CompanyMemory]:
    """
    Update an existing memory item with strict tenant isolation.
    """
    memory = get_company_memory(db=db, company_id=company_id, memory_id=memory_id, update_access_time=False)
    if not memory:
        return None

    if update_in.content is not None:
        validate_no_sensitive_data(update_in.content)
        memory.content = update_in.content.strip()
        provider = get_embedding_provider()
        memory.embedding = provider.embed_text(memory.content)

    if update_in.memory_type is not None:
        memory.memory_type = update_in.memory_type

    if update_in.confidence is not None:
        memory.confidence = update_in.confidence

    if update_in.importance is not None:
        memory.importance = update_in.importance

    if update_in.status is not None:
        memory.status = update_in.status

    if update_in.metadata_payload is not None:
        memory.metadata_payload = update_in.metadata_payload

    memory.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(memory)
    return memory


def supersede_company_memory(
    db: Session,
    company_id: int,
    old_memory_id: int,
    new_memory_in: CompanyMemoryCreate,
    user_id: Optional[int] = None,
) -> Tuple[CompanyMemory, CompanyMemory]:
    """
    Audit-safe supersession lifecycle:
    1. Persist the new active memory item.
    2. Mark the previous memory item as SUPERSEDED and link it to the new item.
    3. Preserves historical memory records for enterprise auditability.
    """
    old_memory = get_company_memory(db=db, company_id=company_id, memory_id=old_memory_id, update_access_time=False)
    if not old_memory:
        raise ValueError(f"Memory {old_memory_id} not found for this company.")

    new_memory = create_company_memory(db=db, company_id=company_id, memory_in=new_memory_in, user_id=user_id)

    old_memory.status = MemoryStatus.SUPERSEDED
    old_memory.superseded_by_id = new_memory.id
    old_memory.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(old_memory)

    return new_memory, old_memory


def delete_company_memory(
    db: Session,
    company_id: int,
    memory_id: int,
    hard_delete: bool = False,
) -> bool:
    """
    Delete or archive a company memory item.
    Defaults to soft-archiving (status = ARCHIVED) to preserve audit trails.
    """
    memory = get_company_memory(db=db, company_id=company_id, memory_id=memory_id, update_access_time=False)
    if not memory:
        return False

    if hard_delete:
        db.delete(memory)
    else:
        memory.status = MemoryStatus.ARCHIVED
        memory.updated_at = datetime.utcnow()

    db.commit()
    return True


def retrieve_relevant_memories(
    db: Session,
    company_id: int,
    query: str,
    memory_type: Optional[MemoryType] = None,
    top_k: int = 5,
    include_candidates: bool = False,
) -> List[RetrievedMemoryItem]:
    """
    Retrieve top-k relevant memories using pgvector cosine distance.
    Enforces tenant isolation: only memories matching company_id participate.
    Excludes SUPERSEDED and ARCHIVED memories.
    """
    if not query or not query.strip():
        return []

    bounded_top_k = max(1, min(50, top_k))
    provider = get_embedding_provider()
    query_vector = provider.embed_text(query.strip())

    distance_expr = CompanyMemory.embedding.cosine_distance(query_vector)

    allowed_statuses = [MemoryStatus.ACTIVE]
    if include_candidates:
        allowed_statuses.append(MemoryStatus.CANDIDATE)

    query_builder = db.query(
        CompanyMemory.id,
        CompanyMemory.company_id,
        CompanyMemory.memory_type,
        CompanyMemory.content,
        CompanyMemory.source,
        CompanyMemory.confidence,
        CompanyMemory.importance,
        CompanyMemory.status,
        distance_expr.label("distance"),
    ).filter(
        CompanyMemory.company_id == company_id,
        CompanyMemory.status.in_(allowed_statuses),
        CompanyMemory.embedding.isnot(None),
    )

    if memory_type:
        query_builder = query_builder.filter(CompanyMemory.memory_type == memory_type)

    results = query_builder.order_by(distance_expr).limit(bounded_top_k).all()

    items: List[RetrievedMemoryItem] = []
    now = datetime.utcnow()
    accessed_ids = []

    for r in results:
        cosine_distance = float(r.distance) if r.distance is not None else 1.0
        similarity_score = max(0.0, min(1.0, round(1.0 - cosine_distance, 4)))
        items.append(
            RetrievedMemoryItem(
                id=r.id,
                company_id=r.company_id,
                memory_type=r.memory_type,
                content=r.content,
                source=r.source,
                confidence=r.confidence,
                importance=r.importance,
                status=r.status,
                similarity_score=similarity_score,
            )
        )
        accessed_ids.append(r.id)

    # Batch update last_accessed_at
    if accessed_ids:
        db.query(CompanyMemory).filter(CompanyMemory.id.in_(accessed_ids)).update(
            {"last_accessed_at": now},
            synchronize_session=False,
        )
        db.commit()

    return items


def resolve_profile_memory_conflicts(
    db: Session,
    company_id: int,
) -> MemoryConflictResolutionResponse:
    """
    Enforces the explicit Precedence Hierarchy:
    EXPLICIT STRUCTURED COMPANY PROFILE > DURABLE LONG-TERM MEMORY.
    
    Inspects active procedural and semantic memories against the verified CompanyAIProfile.
    If a memory directly contradicts the authoritative CompanyAIProfile, the memory
    is marked SUPERSEDED so downstream AI nodes consume the structured profile truth.
    """
    profile = db.query(CompanyAIProfile).filter(CompanyAIProfile.company_id == company_id).first()
    active_memories = list_company_memories(db=db, company_id=company_id, active_only=True)

    if not profile:
        return MemoryConflictResolutionResponse(
            company_id=company_id,
            conflicts_detected=0,
            structured_profile_precedence_applied=True,
            summary="No CompanyAIProfile configured; active memories stand as primary context.",
            active_memory_count=len(active_memories),
        )

    conflicts_detected = 0
    # Check for direct contradictions against authoritative CompanyAIProfile
    profile_voice = (profile.brand_voice or "").strip().lower()
    profile_style = (profile.preferred_writing_style or "").strip().lower()

    for mem in active_memories:
        if mem.memory_type == MemoryType.PROCEDURAL:
            content_lower = mem.content.lower()
            if profile_voice and ("voice" in content_lower or "tone" in content_lower):
                if profile_voice not in content_lower and mem.source != MemorySource.COMPANY_PROFILE:
                    mem.status = MemoryStatus.SUPERSEDED
                    mem.updated_at = datetime.utcnow()
                    conflicts_detected += 1
            elif profile_style and "style" in content_lower:
                if profile_style not in content_lower and mem.source != MemorySource.COMPANY_PROFILE:
                    mem.status = MemoryStatus.SUPERSEDED
                    mem.updated_at = datetime.utcnow()
                    conflicts_detected += 1

    if conflicts_detected > 0:
        db.commit()

    return MemoryConflictResolutionResponse(
        company_id=company_id,
        conflicts_detected=conflicts_detected,
        structured_profile_precedence_applied=True,
        summary=f"Evaluated {len(active_memories)} memories against authoritative CompanyAIProfile. {conflicts_detected} conflicting memories superseded.",
        active_memory_count=len(active_memories) - conflicts_detected,
    )

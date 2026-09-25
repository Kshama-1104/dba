from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.company_memory import MemoryStatus, MemoryType
from backend.app.models.user import User, UserRole
from backend.app.schemas.company_memory import (
    CompanyMemoryCreate,
    CompanyMemoryListResponse,
    CompanyMemoryResponse,
    CompanyMemoryUpdate,
    MemoryConflictResolutionResponse,
    MemoryRetrievalRequest,
    MemoryRetrievalResponse,
)
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

router = APIRouter(
    prefix="/api/v1/company/memory",
    tags=["Company Long-Term Memory"],
)


@router.post(
    "",
    response_model=CompanyMemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record durable long-term memory",
)
def create_memory_endpoint(
    payload: CompanyMemoryCreate,
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Record a new durable memory item (Semantic, Episodic, or Procedural).
    Restricted to Company Admin and Editor roles (Reviewer gets 403).
    Enforces sensitive-data guards and generates dense vector embeddings.
    """
    try:
        memory = create_company_memory(
            db=db,
            company_id=current_user.company_id,
            memory_in=payload,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return memory


@router.get(
    "",
    response_model=CompanyMemoryListResponse,
    summary="List company long-term memories",
)
def list_memories_endpoint(
    memory_type: Optional[MemoryType] = Query(None, description="Filter by memory type"),
    status_filter: Optional[MemoryStatus] = Query(None, alias="status", description="Filter by status"),
    active_only: bool = Query(False, description="Filter only active memories"),
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
    List company memories with optional type and status filtering.
    Enforces tenant isolation: only memories matching authenticated company_id are returned.
    """
    memories = list_company_memories(
        db=db,
        company_id=current_user.company_id,
        memory_type=memory_type,
        status=status_filter,
        active_only=active_only,
    )
    return CompanyMemoryListResponse(
        total=len(memories),
        memories=memories,
    )


@router.get(
    "/{memory_id}",
    response_model=CompanyMemoryResponse,
    summary="Get specific company memory item",
)
def get_memory_endpoint(
    memory_id: int,
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
    Retrieve details of a specific memory item.
    Enforces tenant isolation: returns 404 if memory belongs to another company.
    """
    memory = get_company_memory(
        db=db,
        company_id=current_user.company_id,
        memory_id=memory_id,
    )
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found for this company.",
        )
    return memory


@router.put(
    "/{memory_id}",
    response_model=CompanyMemoryResponse,
    summary="Update company memory item",
)
def update_memory_endpoint(
    memory_id: int,
    payload: CompanyMemoryUpdate,
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Update memory content, category, importance, or status.
    Restricted to Company Admin and Editor roles (Reviewer gets 403).
    """
    try:
        updated = update_company_memory(
            db=db,
            company_id=current_user.company_id,
            memory_id=memory_id,
            update_in=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found for this company.",
        )
    return updated


@router.post(
    "/{memory_id}/supersede",
    response_model=CompanyMemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Supersede an existing memory with updated version",
)
def supersede_memory_endpoint(
    memory_id: int,
    payload: CompanyMemoryCreate,
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Supersede an existing memory:
    Creates a new ACTIVE memory and transitions the old memory to SUPERSEDED, linking them.
    Preserves audit history.
    """
    try:
        new_memory, _ = supersede_company_memory(
            db=db,
            company_id=current_user.company_id,
            old_memory_id=memory_id,
            new_memory_in=payload,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return new_memory


@router.delete(
    "/{memory_id}",
    summary="Archive or delete company memory",
)
def delete_memory_endpoint(
    memory_id: int,
    hard_delete: bool = Query(False, description="Whether to permanently remove record"),
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Archive (default) or hard-delete a company memory item.
    Restricted to Company Admin and Editor roles (Reviewer gets 403).
    Only Company Admin is authorized to perform permanent hard deletion (hard_delete=true).
    """
    if hard_delete and current_user.role != UserRole.COMPANY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Company Admin can hard-delete memory records. Editors may only soft-archive memories.",
        )

    success = delete_company_memory(
        db=db,
        company_id=current_user.company_id,
        memory_id=memory_id,
        hard_delete=hard_delete,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found for this company.",
        )
    action = "deleted" if hard_delete else "archived"
    return {"message": f"Memory {action} successfully", "id": memory_id}


@router.post(
    "/retrieve",
    response_model=MemoryRetrievalResponse,
    summary="Semantic retrieval over company memory base",
)
def retrieve_memories_endpoint(
    payload: MemoryRetrievalRequest,
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
    Retrieve top-k relevant active memories for a given query or context topic.
    Uses pgvector cosine distance filtered strictly to the authenticated company.
    """
    results = retrieve_relevant_memories(
        db=db,
        company_id=current_user.company_id,
        query=payload.query,
        memory_type=payload.memory_type,
        top_k=payload.top_k,
        include_candidates=payload.include_candidates,
    )
    return MemoryRetrievalResponse(
        query=payload.query,
        total_results=len(results),
        memories=results,
    )


@router.post(
    "/resolve-conflicts",
    response_model=MemoryConflictResolutionResponse,
    summary="Enforce structured profile precedence and resolve memory conflicts",
)
def resolve_conflicts_endpoint(
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Evaluates active memories against the authoritative CompanyAIProfile.
    Enforces the precedence rule: Explicit CompanyAIProfile > Long-Term Memory.
    Directly conflicting memories are marked SUPERSEDED.
    """
    return resolve_profile_memory_conflicts(
        db=db,
        company_id=current_user.company_id,
    )

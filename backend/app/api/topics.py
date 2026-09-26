"""
Topic Intelligence API — Phase 5

Endpoints for AI-assisted topic candidate generation, listing,
selection, and rejection.

RBAC rules (from Product Requirements Document):
    Company Admin: VIEW ONLY (list, get)
    Reviewer:      VIEW ONLY (list, get)
    Editor:        FULL (generate, list, get, select, reject)

Topic selection does NOT trigger blog generation.
This is the Phase 5 boundary — blog generation is Phase 6.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.topic_candidate import TopicStatus
from backend.app.models.user import User, UserRole
from backend.app.schemas.topic import (
    TopicCandidateCreate,
    TopicCandidateResponse,
    TopicGenerateRequest,
)
from backend.app.services.topic_service import TopicIntelligenceService


router = APIRouter(
    prefix="/api/v1/company/topics",
    tags=["Topic Intelligence"],
)


@router.post(
    "/custom",
    response_model=TopicCandidateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom topic candidate",
)
def create_custom_topic(
    topic_in: TopicCandidateCreate,
    current_user: User = Depends(
        require_role(UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """
    Allow an Editor to supply a custom topic candidate (PRD Section 16.3).

    Only Editors may create custom topics (Company Admin and Reviewer get 403).
    Deduplication is applied. Status is stored as SUGGESTED.
    Topic creation does NOT trigger blog generation (Phase 5 boundary).
    """
    service = TopicIntelligenceService(db=db)
    try:
        return service.create_custom_topic(
            company_id=current_user.company_id,
            topic_in=topic_in,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create custom topic.",
        ) from exc


@router.post(
    "/generate",
    response_model=List[TopicCandidateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI topic candidates",
)
def generate_topics(
    payload: Optional[TopicGenerateRequest] = None,
    current_user: User = Depends(
        require_role(UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """
    Generate 3–5 topic candidates using the company's assembled context:
    Company AI Profile + Knowledge/RAG + Long-Term Memory + Topic History + optional Editor focus.

    Only Editors may generate topics (Company Admin and Reviewer get 403).

    Returns candidates ranked by final_score (relevance + freshness) descending.
    If insufficient company context exists, returns an empty list.

    Topic generation does NOT trigger blog creation (Phase 5 boundary).
    """
    service = TopicIntelligenceService(db=db)
    focus_theme = payload.focus_theme if payload else None
    target_keyword = payload.target_keyword if payload else None
    try:
        candidates = service.generate_topics(
            company_id=current_user.company_id,
            user_id=current_user.id,
            focus_theme=focus_theme,
            target_keyword=target_keyword,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Topic generation failed. Please try again.",
        ) from exc

    return candidates


@router.get(
    "",
    response_model=List[TopicCandidateResponse],
    summary="List topic candidates",
)
def list_topics(
    status_filter: Optional[TopicStatus] = Query(
        None,
        alias="status",
        description="Filter by topic status",
    ),
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
    List all topic candidates for the authenticated company.
    All roles (Admin, Editor, Reviewer) may view topics.
    Optionally filter by status.
    """
    service = TopicIntelligenceService(db=db)
    return service.list_topics(
        company_id=current_user.company_id,
        status_filter=status_filter,
    )


@router.get(
    "/{topic_id}",
    response_model=TopicCandidateResponse,
    summary="Get topic candidate details",
)
def get_topic(
    topic_id: int,
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
    Retrieve a specific topic candidate by ID.
    Enforces tenant isolation: returns 404 if topic belongs to another company.
    """
    service = TopicIntelligenceService(db=db)
    topic = service.get_topic(
        company_id=current_user.company_id,
        topic_id=topic_id,
    )
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic {topic_id} not found for this company.",
        )
    return topic


@router.post(
    "/{topic_id}/select",
    response_model=TopicCandidateResponse,
    summary="Select a topic candidate",
)
def select_topic(
    topic_id: int,
    current_user: User = Depends(
        require_role(UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """
    Transition a topic from SUGGESTED to SELECTED.

    Only Editors may select topics.
    Selection does NOT trigger blog generation (Phase 5 boundary).
    """
    service = TopicIntelligenceService(db=db)
    try:
        return service.select_topic(
            company_id=current_user.company_id,
            topic_id=topic_id,
            user=current_user,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{topic_id}/reject",
    response_model=TopicCandidateResponse,
    summary="Reject a topic candidate",
)
def reject_topic(
    topic_id: int,
    current_user: User = Depends(
        require_role(UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """
    Transition a topic to REJECTED.

    Only Editors may reject topics.
    Rejected topics will not be re-suggested (they remain in duplicate detection).
    """
    service = TopicIntelligenceService(db=db)
    try:
        return service.reject_topic(
            company_id=current_user.company_id,
            topic_id=topic_id,
            user=current_user,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

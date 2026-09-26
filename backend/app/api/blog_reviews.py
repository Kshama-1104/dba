"""
Blog Reviewer Workflow API — Phase 9

Endpoints for human editorial review, submission gating, shared reviewer queue,
Separation of Duties (SoD), and review lifecycle decisions.

RBAC:
    POST submit-for-review:  Editor, Company Admin
    POST withdraw-review:    Editor, Company Admin
    GET reviews/pending:     Reviewer, Company Admin
    GET blog reviews:        Reviewer, Editor, Company Admin
    GET review detail:       Reviewer, Editor, Company Admin
    POST decide review:      Reviewer, Company Admin
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole
from backend.app.schemas.blog_review import (
    BlogReviewDecisionRequest,
    BlogReviewDetailResponse,
    BlogReviewResponse,
    BlogSubmitForReviewRequest,
    PendingReviewItemResponse,
)
from backend.app.services.blog_review_service import BlogReviewService

router = APIRouter(
    prefix="/api/v1/blogs",
    tags=["Blog Reviewer Workflow"],
)


# ── 1. Shared Pending Review Queue ──────────────────────────────────────
# Note: Defined before /{blog_id} to avoid path collision

@router.get(
    "/reviews/pending",
    response_model=List[PendingReviewItemResponse],
    summary="List pending reviews in the shared company reviewer queue",
)
def list_pending_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.REVIEWER)
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve all blog reviews in 'pending' status for the caller's company.
    Ordered by submission time ascending (FIFO).
    """
    service = BlogReviewService(db=db)
    items = service.list_pending_reviews(
        company_id=current_user.company_id,
        skip=skip,
        limit=limit,
    )
    return [PendingReviewItemResponse.model_validate(item) for item in items]


# ── 2. Submit for Review ────────────────────────────────────────────────

@router.post(
    "/{blog_id}/submit-for-review",
    response_model=BlogReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a blog draft for human editorial review",
)
def submit_for_review(
    blog_id: int,
    request: Optional[BlogSubmitForReviewRequest] = None,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """
    Submits blog draft for review. Executes deterministic Phase 7 format and SEO
    validation gating before allowing the submission. Creates a new BlogReview record
    bound to the latest immutable BlogRevision.
    """
    service = BlogReviewService(db=db)
    review = service.submit_for_review(
        company_id=current_user.company_id,
        blog_id=blog_id,
        user=current_user,
        request=request,
    )
    return BlogReviewResponse.model_validate(review)


# ── 3. Withdraw Submission ──────────────────────────────────────────────

@router.post(
    "/{blog_id}/withdraw-review",
    response_model=BlogReviewResponse,
    summary="Withdraw a pending review submission back to DRAFT",
)
def withdraw_review(
    blog_id: int,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """
    Withdraws a pending review submission. Marks review cycle as 'withdrawn'
    and resets the blog status to 'draft'.
    """
    service = BlogReviewService(db=db)
    review = service.withdraw_submission(
        company_id=current_user.company_id,
        blog_id=blog_id,
        user=current_user,
    )
    return BlogReviewResponse.model_validate(review)


# ── 4. Review History ───────────────────────────────────────────────────

@router.get(
    "/{blog_id}/reviews",
    response_model=List[BlogReviewResponse],
    summary="Get all review cycles for a blog draft",
)
def get_review_history(
    blog_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR, UserRole.REVIEWER)
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve chronological list of all review cycles for the specified blog.
    """
    service = BlogReviewService(db=db)
    reviews = service.get_review_history(
        company_id=current_user.company_id,
        blog_id=blog_id,
        skip=skip,
        limit=limit,
    )
    return [BlogReviewResponse.model_validate(r) for r in reviews]


# ── 5. Review Detail ────────────────────────────────────────────────────

@router.get(
    "/{blog_id}/reviews/{review_id}",
    response_model=BlogReviewDetailResponse,
    summary="Get single review cycle record with detailed context",
)
def get_review_detail(
    blog_id: int,
    review_id: int,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR, UserRole.REVIEWER)
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve single review cycle record by review ID.
    """
    service = BlogReviewService(db=db)
    detail = service.get_review_detail(
        company_id=current_user.company_id,
        blog_id=blog_id,
        review_id=review_id,
    )
    return BlogReviewDetailResponse.model_validate(detail)


# ── 6. Decide Review ────────────────────────────────────────────────────

@router.post(
    "/{blog_id}/reviews/{review_id}/decide",
    response_model=BlogReviewResponse,
    summary="Render an editorial review decision (approve, request_changes, reject)",
)
def decide_review(
    blog_id: int,
    review_id: int,
    request: BlogReviewDecisionRequest,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.REVIEWER)
    ),
    db: Session = Depends(get_db),
):
    """
    Apply editorial decision to a pending review cycle.
    Enforces Separation of Duties (SoD) and atomic validation of submitted revision.
    If 'request_changes' is selected, feedback is injected into the Phase 8 editor chat thread.
    """
    service = BlogReviewService(db=db)
    review = service.decide_review(
        company_id=current_user.company_id,
        blog_id=blog_id,
        review_id=review_id,
        reviewer=current_user,
        request=request,
    )
    return BlogReviewResponse.model_validate(review)

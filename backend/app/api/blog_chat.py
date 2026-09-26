"""
Blog Chat & Revisions API — Phase 8

Endpoints for conversational editor interactions, blog revisions, and lossless rollback.

RBAC:
    GET chat history:       Company Admin, Editor, Reviewer
    POST chat revision:     Editor ONLY
    GET revisions:          Company Admin, Editor, Reviewer
    GET revision detail:    Company Admin, Editor, Reviewer
    POST restore revision:  Editor ONLY
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.core.workflow_guards import verify_blog_editable_for_mutation
from backend.app.models.blog import Blog
from backend.app.models.user import User, UserRole
from backend.app.schemas.blog_chat import (
    BlogChatMessageResponse,
    BlogChatRequest,
    BlogChatResponse,
    BlogChatThreadResponse,
    BlogRestoreRequest,
    BlogRevisionDetailResponse,
    BlogRevisionSummaryResponse,
)
from backend.app.services.blog_revision_service import BlogRevisionService

router = APIRouter(
    prefix="/api/v1/blogs/{blog_id}",
    tags=["Blog Chat & Revisions"],
)


@router.get(
    "/chat",
    response_model=BlogChatThreadResponse,
    summary="Get conversation thread and chat history for a blog draft",
)
def get_chat_history(
    blog_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR, UserRole.REVIEWER)
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve conversational editing thread metadata and chronologically ordered messages.
    
    RBAC:
        Company Admin, Editor, Reviewer allowed.
        Strict tenant isolation: Cross-tenant blog IDs return 404 Not Found.
    """
    service = BlogRevisionService(db=db)
    thread, messages = service.get_chat_history(
        company_id=current_user.company_id,
        blog_id=blog_id,
        skip=skip,
        limit=limit,
    )
    return BlogChatThreadResponse(
        id=thread.id,
        company_id=thread.company_id,
        blog_id=thread.blog_id,
        editor_id=thread.editor_id,
        status=thread.status,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        closed_at=thread.closed_at,
        messages=[BlogChatMessageResponse.model_validate(m) for m in messages],
    )


@router.post(
    "/chat",
    response_model=BlogChatResponse,
    summary="Send an editor instruction to revise the blog draft",
)
def post_chat_message(
    blog_id: int,
    request: BlogChatRequest,
    current_user: User = Depends(require_role(UserRole.EDITOR)),
    _blog: Blog = Depends(verify_blog_editable_for_mutation),
    db: Session = Depends(get_db),
):
    """
    Submit an editorial instruction to revise the current blog draft.
    
    RBAC:
        Editor ONLY. Company Admin and Reviewer receive 403 Forbidden.
        
    Guarantees:
        - Atomic revision creation (V_N+1) upon Phase 7 validation pass.
        - Concurrency check against base_revision_id (409 Conflict if stale).
        - Idempotency via client_message_id.
        - Non-LLM deterministic target detection and surgical integrity audit.
        - Unchanged blog state on Phase 7 validation failure (422 Unprocessable Entity).
    """
    service = BlogRevisionService(db=db)
    return service.process_chat_revision(
        company_id=current_user.company_id,
        blog_id=blog_id,
        user=current_user,
        request=request,
    )


@router.get(
    "/revisions",
    response_model=List[BlogRevisionSummaryResponse],
    summary="List all historical revisions for a blog draft",
)
def list_revisions(
    blog_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR, UserRole.REVIEWER)
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve chronological revision history for this blog (V0, V1, V2, etc.).
    
    RBAC:
        Company Admin, Editor, Reviewer allowed.
    """
    service = BlogRevisionService(db=db)
    revisions = service.get_revisions(
        company_id=current_user.company_id,
        blog_id=blog_id,
        skip=skip,
        limit=limit,
    )
    return [BlogRevisionSummaryResponse.model_validate(r) for r in revisions]


@router.get(
    "/revisions/{revision_id}",
    response_model=BlogRevisionDetailResponse,
    summary="Get full details of a specific blog revision snapshot",
)
def get_revision_detail(
    blog_id: int,
    revision_id: int,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR, UserRole.REVIEWER)
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve complete snapshot detail of a revision, including StructuredBlogDraft JSON AST,
    rendered Markdown, and Phase 7 validation report.
    
    RBAC:
        Company Admin, Editor, Reviewer allowed.
    """
    service = BlogRevisionService(db=db)
    revision = service.get_revision_detail(
        company_id=current_user.company_id,
        blog_id=blog_id,
        revision_id=revision_id,
    )
    return BlogRevisionDetailResponse.model_validate(revision)


@router.post(
    "/revisions/{revision_id}/restore",
    response_model=BlogRevisionDetailResponse,
    summary="Restore a historical revision as a new snapshot",
)
def restore_revision(
    blog_id: int,
    revision_id: int,
    request: Optional[BlogRestoreRequest] = None,
    current_user: User = Depends(require_role(UserRole.EDITOR)),
    _blog: Blog = Depends(verify_blog_editable_for_mutation),
    db: Session = Depends(get_db),
):
    """
    Losslessly restore a previous revision (e.g. restore V1 from current V3).
    A new revision V4 is created with content from V1 and restored_from_revision_id = V1.id.
    Historical revisions are never deleted.
    
    RBAC:
        Editor ONLY. Company Admin and Reviewer receive 403 Forbidden.
    """
    service = BlogRevisionService(db=db)
    new_rev, _ = service.restore_revision(
        company_id=current_user.company_id,
        blog_id=blog_id,
        revision_id=revision_id,
        user=current_user,
        custom_summary=request.restore_summary if request else None,
    )
    return BlogRevisionDetailResponse.model_validate(new_rev)

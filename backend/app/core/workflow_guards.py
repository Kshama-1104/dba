"""
Workflow and state transition guards for editorial lifecycle and concurrency control.
"""

from datetime import datetime
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.blog import Blog, BlogStatus
from backend.app.models.blog_chat import BlogChatThread, BlogRevision
from backend.app.models.user import User, UserRole
from backend.app.services.blog_revision_service import BlogRevisionService


def verify_blog_editable_for_mutation(
    blog_id: int,
    current_user: User = Depends(require_role(UserRole.EDITOR)),
    db: Session = Depends(get_db),
) -> Blog:
    """
    FastAPI dependency guard ensuring a blog can be edited or mutated.
    Acquires an exclusive row lock (FOR UPDATE) within the current transaction.
    
    Guarantees:
    - Tenant isolation: cross-tenant access returns 404 Not Found.
    - Status enforcement: only 'draft' and 'changes_requested' can be mutated.
      Any blog in 'pending_review', 'approved', 'rejected', or 'generating' returns 409 Conflict.
    - Concurrency integrity: Pre-warms chat thread and V0 prerequisites before acquiring the
      atomic row lock, ensuring downstream Phase 8 services execute zero intermediate commits
      that would prematurely release the row lock before final mutation.
    """
    # 1. Quick initial existence and tenant check
    blog_check = (
        db.query(Blog)
        .filter(Blog.id == blog_id, Blog.company_id == current_user.company_id)
        .first()
    )
    if not blog_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found",
        )

    if blog_check.status not in (BlogStatus.DRAFT, BlogStatus.CHANGES_REQUESTED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Blog cannot be modified while in status '{blog_check.status.value}'. "
                "Edits and revisions are only permitted when status is 'draft' or 'changes_requested'."
            ),
        )

    # 2. Pre-warm prerequisites outside the row-lock critical section
    thread = (
        db.query(BlogChatThread)
        .filter(
            BlogChatThread.blog_id == blog_id,
            BlogChatThread.company_id == current_user.company_id,
        )
        .first()
    )
    if not thread:
        thread = BlogChatThread(
            company_id=current_user.company_id,
            blog_id=blog_id,
            editor_id=current_user.id,
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(thread)
        db.commit()

    v0 = (
        db.query(BlogRevision)
        .filter(
            BlogRevision.blog_id == blog_id,
            BlogRevision.company_id == current_user.company_id,
            BlogRevision.revision_number == 0,
        )
        .first()
    )
    if not v0:
        rev_service = BlogRevisionService(db=db)
        rev_service.ensure_initial_revision_v0(blog=blog_check, editor_id=current_user.id)

    # 3. Enter atomic critical section with row lock (FOR UPDATE)
    blog = (
        db.query(Blog)
        .filter(Blog.id == blog_id, Blog.company_id == current_user.company_id)
        .with_for_update()
        .first()
    )
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found",
        )

    if blog.status not in (BlogStatus.DRAFT, BlogStatus.CHANGES_REQUESTED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Blog cannot be modified while in status '{blog.status.value}'. "
                "Edits and revisions are only permitted when status is 'draft' or 'changes_requested'."
            ),
        )

    return blog

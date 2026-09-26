"""
Phase 9 — Human Reviewer Workflow & Editorial Governance Service.

Orchestrates human review lifecycles:
1. Submission with atomic Phase 7 validation gating.
2. Withdrawal of pending review back to DRAFT.
3. Review decisions (APPROVE, REQUEST_CHANGES, REJECT) with Separation of Duties (SoD).
4. Injection of editorial feedback into Phase 8 chat thread.
5. Strict tenant isolation and concurrency row locks.
"""

from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.blog import Blog, BlogStatus
from backend.app.models.blog_chat import (
    BlogChatMessage,
    BlogChatThread,
    BlogRevision,
    ChatSenderType,
    ThreadStatus,
)
from backend.app.models.blog_format import BlogFormat
from backend.app.models.blog_review import BlogReview, ReviewStatus
from backend.app.models.user import User, UserRole, UserStatus
from backend.app.schemas.blog_review import (
    BlogReviewDecisionRequest,
    BlogSubmitForReviewRequest,
    ReviewDecision,
)
from backend.app.services.blog_revision_service import BlogRevisionService
from backend.app.services.blog_validation_service import BlogValidationService

logger = logging.getLogger(__name__)


class BlogReviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def submit_for_review(
        self,
        company_id: int,
        blog_id: int,
        user: User,
        request: Optional[BlogSubmitForReviewRequest] = None,
    ) -> BlogReview:
        """
        Submit a blog draft for human editorial review.

        Invariants enforced:
        - Strict tenant isolation (returns 404 if not found in company).
        - State check: Only 'draft' or 'changes_requested' can be submitted (409 if in other status).
        - Single active review cycle: 409 if an active pending review already exists.
        - Automatic V0 revision snapshot creation if no revisions exist yet.
        - Immutable submitted_revision_id bound to the latest revision.
        - Atomic Phase 7 validation gating: Blog must pass Phase 7 deterministic format and SEO validation (422 if failed).
        - Transitions blog to 'pending_review'.
        """
        # 1. Quick initial existence and tenant check
        blog_check = (
            self.db.query(Blog)
            .filter(Blog.id == blog_id, Blog.company_id == company_id)
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
                    f"Blog cannot be submitted for review from status '{blog_check.status.value}'. "
                    "Only blogs in 'draft' or 'changes_requested' can be submitted."
                ),
            )

        # 2. Pre-warm V0 revision snapshot outside the atomic row-lock critical section
        latest_rev = (
            self.db.query(BlogRevision)
            .filter(BlogRevision.blog_id == blog_id, BlogRevision.company_id == company_id)
            .order_by(BlogRevision.revision_number.desc())
            .first()
        )
        if not latest_rev:
            rev_service = BlogRevisionService(db=self.db)
            rev_service.ensure_initial_revision_v0(
                blog=blog_check,
                editor_id=user.id,
            )

        # 3. Enter atomic critical section with row lock (FOR UPDATE)
        blog = (
            self.db.query(Blog)
            .filter(Blog.id == blog_id, Blog.company_id == company_id)
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
                    f"Blog cannot be submitted for review from status '{blog.status.value}'. "
                    "Only blogs in 'draft' or 'changes_requested' can be submitted."
                ),
            )

        # Check for active pending review under the lock
        existing_pending = (
            self.db.query(BlogReview)
            .filter(
                BlogReview.blog_id == blog.id,
                BlogReview.company_id == company_id,
                BlogReview.status == ReviewStatus.PENDING.value,
            )
            .first()
        )
        if existing_pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Blog already has an active pending review.",
            )

        # Authoritatively query latest revision under the lock
        latest_rev = (
            self.db.query(BlogRevision)
            .filter(BlogRevision.blog_id == blog.id, BlogRevision.company_id == company_id)
            .order_by(BlogRevision.revision_number.desc())
            .first()
        )

        # Phase 7 Validation Gating
        active_format = (
            self.db.query(BlogFormat)
            .filter(BlogFormat.company_id == company_id)
            .first()
        )
        validation_service = BlogValidationService(db=self.db)
        validation_result = validation_service.validate_blog(
            blog=blog,
            active_format=active_format,
            persist=False,
        )
        if not validation_result.passed:
            error_messages = [f.message for f in validation_result.errors]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Blog failed Phase 7 deterministic validation and cannot be submitted for review.",
                    "errors": error_messages,
                    "findings": [f.model_dump() for f in validation_result.errors],
                },
            )

        # Transition blog status and update validation metadata atomically
        current_metadata = dict(blog.generation_metadata or {})
        current_metadata["validation"] = json.loads(validation_result.model_dump_json())
        blog.generation_metadata = current_metadata
        blog.updated_at = datetime.utcnow()
        blog.status = BlogStatus.PENDING_REVIEW

        review = BlogReview(
            company_id=company_id,
            blog_id=blog.id,
            submitted_revision_id=latest_rev.id,
            reviewer_id=None,
            status=ReviewStatus.PENDING.value,
            submission_note=request.submission_note if request else None,
            submitted_at=datetime.utcnow(),
        )
        self.db.add(blog)
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def withdraw_submission(
        self,
        company_id: int,
        blog_id: int,
        user: User,
    ) -> BlogReview:
        """
        Withdraw a pending review submission.
        
        Invariants enforced:
        - Strict tenant isolation (404).
        - Blog must be in 'pending_review' (409 if not).
        - Pending review row marked 'withdrawn' with decided_at timestamp.
        - Blog status returned to 'draft'.
        """
        blog = (
            self.db.query(Blog)
            .filter(Blog.id == blog_id, Blog.company_id == company_id)
            .with_for_update()
            .first()
        )
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found",
            )

        if blog.status != BlogStatus.PENDING_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot withdraw review for blog in status '{blog.status.value}'. Blog is not pending review.",
            )

        review = (
            self.db.query(BlogReview)
            .filter(
                BlogReview.blog_id == blog.id,
                BlogReview.company_id == company_id,
                BlogReview.status == ReviewStatus.PENDING.value,
            )
            .with_for_update()
            .first()
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pending review found for this blog.",
            )

        review.status = ReviewStatus.WITHDRAWN.value
        review.decided_at = datetime.utcnow()
        blog.status = BlogStatus.DRAFT

        self.db.commit()
        self.db.refresh(review)
        return review

    def decide_review(
        self,
        company_id: int,
        blog_id: int,
        review_id: int,
        reviewer: User,
        request: BlogReviewDecisionRequest,
    ) -> BlogReview:
        """
        Render an editorial decision on a pending review cycle.

        Decisions:
        - APPROVE: Blog status -> 'approved', review status -> 'approved'.
        - REQUEST_CHANGES: Blog status -> 'changes_requested', review status -> 'changes_requested',
          injects editorial feedback into Phase 8 chat thread.
        - REJECT: Blog status -> 'rejected', review status -> 'rejected'.

        Invariants enforced:
        - Strict tenant isolation.
        - Blog and Review row locks (FOR UPDATE).
        - Separation of Duties (SoD): Authors cannot review their own blogs (403),
          unless single-user break-glass tenant where user is the only active company user.
        - Immutable revision check: Submitted revision must still match current latest revision (409 if diverged).
        """
        blog = (
            self.db.query(Blog)
            .filter(Blog.id == blog_id, Blog.company_id == company_id)
            .with_for_update()
            .first()
        )
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found",
            )

        review = (
            self.db.query(BlogReview)
            .filter(
                BlogReview.id == review_id,
                BlogReview.blog_id == blog_id,
                BlogReview.company_id == company_id,
            )
            .with_for_update()
            .first()
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review record not found",
            )

        if review.status != ReviewStatus.PENDING.value or blog.status != BlogStatus.PENDING_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Review is no longer pending or blog is not in 'pending_review' status.",
            )

        # Separation of Duties check
        if blog.created_by_user_id is not None and blog.created_by_user_id == reviewer.id:
            active_users_count = (
                self.db.query(User)
                .filter(User.company_id == company_id, User.status == UserStatus.ACTIVE)
                .count()
            )
            is_solo_admin = (active_users_count <= 1 and reviewer.role == UserRole.COMPANY_ADMIN)
            if not is_solo_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Separation of Duties violation: Authors cannot review or decide upon their own blogs.",
                )

        # Verify submitted revision integrity
        latest_rev = (
            self.db.query(BlogRevision)
            .filter(BlogRevision.blog_id == blog.id, BlogRevision.company_id == company_id)
            .order_by(BlogRevision.revision_number.desc())
            .first()
        )
        if not latest_rev or latest_rev.id != review.submitted_revision_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Review applies to a superseded revision. Blog has diverged since review submission.",
            )

        # Apply decision
        now = datetime.utcnow()
        review.reviewer_id = reviewer.id
        review.decided_at = now
        review.reviewer_comment = request.reviewer_comment
        review.feedback = request.feedback

        if request.decision == ReviewDecision.APPROVE:
            review.status = ReviewStatus.APPROVED.value
            blog.status = BlogStatus.APPROVED

        elif request.decision == ReviewDecision.REJECT:
            review.status = ReviewStatus.REJECTED.value
            blog.status = BlogStatus.REJECTED

        elif request.decision == ReviewDecision.REQUEST_CHANGES:
            review.status = ReviewStatus.CHANGES_REQUESTED.value
            blog.status = BlogStatus.CHANGES_REQUESTED

            # Inject editorial feedback into Phase 8 chat thread
            thread = (
                self.db.query(BlogChatThread)
                .filter(
                    BlogChatThread.blog_id == blog.id,
                    BlogChatThread.company_id == company_id,
                )
                .first()
            )
            if not thread:
                target_editor_id = blog.created_by_user_id or reviewer.id
                thread = BlogChatThread(
                    company_id=company_id,
                    blog_id=blog.id,
                    editor_id=target_editor_id,
                    status=ThreadStatus.ACTIVE.value,
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(thread)
                self.db.flush()

            feedback_msg = BlogChatMessage(
                thread_id=thread.id,
                sender_type=ChatSenderType.SYSTEM.value,
                sender_id=reviewer.id,
                message_type="review_feedback",
                content=f"Editorial Review Feedback: {request.feedback}",
                message_metadata={
                    "review_id": review.id,
                    "decision": "changes_requested",
                    "reviewer_id": reviewer.id,
                    "submitted_revision_id": review.submitted_revision_id,
                },
                created_at=now,
            )
            self.db.add(feedback_msg)

        self.db.commit()
        self.db.refresh(review)
        return review

    def list_pending_reviews(
        self,
        company_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List all pending reviews in the shared company reviewer queue.
        Ordered by submitted_at ASC (oldest first).
        """
        rows = (
            self.db.query(BlogReview, Blog, BlogRevision)
            .join(Blog, Blog.id == BlogReview.blog_id)
            .join(BlogRevision, BlogRevision.id == BlogReview.submitted_revision_id)
            .filter(
                BlogReview.company_id == company_id,
                BlogReview.status == ReviewStatus.PENDING.value,
            )
            .order_by(BlogReview.submitted_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        results = []
        for review, blog, revision in rows:
            results.append(
                {
                    "review_id": review.id,
                    "blog_id": blog.id,
                    "blog_title": blog.title,
                    "submitted_revision_id": revision.id,
                    "submitted_revision_number": revision.revision_number,
                    "submitted_by_user_id": blog.created_by_user_id,
                    "submission_note": review.submission_note,
                    "submitted_at": review.submitted_at,
                    "status": review.status,
                }
            )
        return results

    def get_review_history(
        self,
        company_id: int,
        blog_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> List[BlogReview]:
        """
        Get all review cycles for a blog in chronological order.
        """
        blog = (
            self.db.query(Blog)
            .filter(Blog.id == blog_id, Blog.company_id == company_id)
            .first()
        )
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found",
            )

        reviews = (
            self.db.query(BlogReview)
            .filter(
                BlogReview.blog_id == blog_id,
                BlogReview.company_id == company_id,
            )
            .order_by(BlogReview.submitted_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return reviews

    def get_review_detail(
        self,
        company_id: int,
        blog_id: int,
        review_id: int,
    ) -> Dict[str, Any]:
        """
        Get single review cycle record with detailed context.
        """
        row = (
            self.db.query(BlogReview, Blog, BlogRevision)
            .join(Blog, Blog.id == BlogReview.blog_id)
            .join(BlogRevision, BlogRevision.id == BlogReview.submitted_revision_id)
            .filter(
                BlogReview.id == review_id,
                BlogReview.blog_id == blog_id,
                BlogReview.company_id == company_id,
            )
            .first()
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review record not found",
            )

        review, blog, revision = row
        return {
            "id": review.id,
            "company_id": review.company_id,
            "blog_id": review.blog_id,
            "submitted_revision_id": review.submitted_revision_id,
            "submitted_revision_number": revision.revision_number,
            "submitted_by_user_id": blog.created_by_user_id,
            "blog_title": blog.title,
            "reviewer_id": review.reviewer_id,
            "status": review.status,
            "submission_note": review.submission_note,
            "feedback": review.feedback,
            "reviewer_comment": review.reviewer_comment,
            "submitted_at": review.submitted_at,
            "decided_at": review.decided_at,
            "created_at": review.created_at,
            "updated_at": review.updated_at,
        }

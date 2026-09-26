"""Pydantic schemas for Phase 9 — Human Reviewer Workflow & Editorial Governance."""

from datetime import datetime
import enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReviewDecision(str, enum.Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class BlogSubmitForReviewRequest(BaseModel):
    """Payload to submit a blog for editorial review."""
    submission_note: Optional[str] = Field(None, max_length=2000, description="Optional note from author/editor to reviewer")


class BlogReviewDecisionRequest(BaseModel):
    """Payload for reviewer decision."""
    decision: ReviewDecision = Field(..., description="Editorial review decision: approve, request_changes, or reject")
    feedback: Optional[str] = Field(None, max_length=10000, description="Mandatory revision instructions if requesting changes")
    reviewer_comment: Optional[str] = Field(None, max_length=5000, description="Optional internal comment or feedback")

    @model_validator(mode="after")
    def validate_decision_feedback(self) -> "BlogReviewDecisionRequest":
        if self.decision == ReviewDecision.REQUEST_CHANGES:
            if not self.feedback or not self.feedback.strip():
                raise ValueError("Editorial feedback is mandatory when requesting changes.")
        elif self.decision == ReviewDecision.REJECT:
            has_feedback = bool(self.feedback and self.feedback.strip())
            has_comment = bool(self.reviewer_comment and self.reviewer_comment.strip())
            if not (has_feedback or has_comment):
                raise ValueError("Reviewer feedback or comment is mandatory when rejecting a blog draft.")
        return self


class BlogReviewResponse(BaseModel):
    """Single blog review cycle record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    blog_id: int
    submitted_revision_id: int
    reviewer_id: Optional[int] = None
    status: str
    submission_note: Optional[str] = None
    feedback: Optional[str] = None
    reviewer_comment: Optional[str] = None
    submitted_at: datetime
    decided_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class BlogReviewDetailResponse(BlogReviewResponse):
    """Detailed review response with revision metadata."""
    submitted_revision_number: Optional[int] = None
    submitted_by_user_id: Optional[int] = None
    blog_title: Optional[str] = None


class PendingReviewItemResponse(BaseModel):
    """Item in shared pending reviewer queue."""
    model_config = ConfigDict(from_attributes=True)

    review_id: int
    blog_id: int
    blog_title: str
    submitted_revision_id: int
    submitted_revision_number: int
    submitted_by_user_id: Optional[int] = None
    submission_note: Optional[str] = None
    submitted_at: datetime
    status: str

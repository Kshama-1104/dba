"""
SQLAlchemy model for Phase 9 — Human Reviewer Workflow & Editorial Governance.
"""

from datetime import datetime
import enum
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class BlogReview(Base):
    __tablename__ = "blog_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    blog_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("blogs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submitted_revision_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("blog_revisions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ReviewStatus.PENDING.value, index=True)
    submission_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rescheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    company = relationship("Company")
    blog = relationship("Blog", back_populates="reviews")
    submitted_revision = relationship("BlogRevision", foreign_keys=[submitted_revision_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])

    __table_args__ = (
        Index("ix_blog_reviews_company_status", "company_id", "status"),
        Index("ix_blog_reviews_blog_submitted_at", "blog_id", "submitted_at"),
    )

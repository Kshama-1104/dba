import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class BlogStatus(str, enum.Enum):
    GENERATING = "generating"
    DRAFT = "draft"
    GENERATION_FAILED = "generation_failed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class Blog(Base):
    __tablename__ = "blogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("topic_candidates.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    primary_keyword: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seo_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[BlogStatus] = mapped_column(
        Enum(
            BlogStatus,
            name="blogstatus",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            native_enum=True,
        ),
        nullable=False,
        default=BlogStatus.DRAFT,
        index=True,
    )
    format_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    generation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    company = relationship("Company", backref="blogs")
    topic_candidate = relationship("TopicCandidate", backref="blog", uselist=False)
    creator = relationship("User", foreign_keys=[created_by_user_id])
    reviews = relationship("BlogReview", back_populates="blog", cascade="all, delete-orphan", order_by="BlogReview.submitted_at.asc()")


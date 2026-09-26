import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base

class TopicStatus(str, enum.Enum):
    SUGGESTED = "suggested"
    SELECTED = "selected"
    REJECTED = "rejected"
    USED = "used"
    EXPIRED = "expired"

class TopicCandidate(Base):
    __tablename__ = "topic_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    angle: Mapped[str] = mapped_column(Text, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str] = mapped_column(String(255), nullable=True)
    source_context: Mapped[str] = mapped_column(Text, nullable=True)
    primary_keyword: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=True)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[TopicStatus] = mapped_column(
        Enum(
            TopicStatus,
            name="topicstatus",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            native_enum=True,
        ),
        nullable=False,
        default=TopicStatus.SUGGESTED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship("Company", backref="topic_candidates")
    creator = relationship("User", foreign_keys=[created_by])

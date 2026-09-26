"""
SQLAlchemy models for Phase 8 — Editor Chat & Blog Revisions.

Encompasses:
1. BlogChatThread — Strict 1:1 conversation thread per blog cycle.
2. BlogChatMessage — Chronological messages within the active thread.
3. BlogRevision — Lossless, append-only historical snapshots of blog content.
"""

from datetime import datetime
import enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class ChatSenderType(str, enum.Enum):
    EDITOR = "editor"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessageType(str, enum.Enum):
    TEXT = "text"
    REVISION_REQUEST = "revision_request"
    REVISION_APPLIED = "revision_applied"
    VALIDATION_WARNING = "validation_warning"
    ROLLBACK_APPLIED = "rollback_applied"


class ThreadStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class BlogChatThread(Base):
    __tablename__ = "blog_chat_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    blog_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("blogs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    editor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    company = relationship("Company")
    blog = relationship("Blog", backref="chat_thread")
    editor = relationship("User", foreign_keys=[editor_id])
    messages = relationship(
        "BlogChatMessage", back_populates="thread", cascade="all, delete-orphan", order_by="BlogChatMessage.created_at"
    )

    __table_args__ = (
        UniqueConstraint("blog_id", name="uq_blog_chat_thread_blog_id"),
        Index("ix_blog_chat_threads_company_blog", "company_id", "blog_id"),
    )


class BlogChatMessage(Base):
    __tablename__ = "blog_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("blog_chat_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sender_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    client_message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    message_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    thread = relationship("BlogChatThread", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])

    __table_args__ = (
        Index("ix_blog_chat_messages_thread_created", "thread_id", "created_at"),
    )


class BlogRevision(Base):
    __tablename__ = "blog_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    blog_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("blogs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    thread_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("blog_chat_threads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("blog_chat_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    editor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_summary: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    seo_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_keyword: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    restored_from_revision_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("blog_revisions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    validation_report: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    company = relationship("Company")
    blog = relationship("Blog", backref="revisions")
    thread = relationship("BlogChatThread")
    message = relationship("BlogChatMessage")
    editor = relationship("User", foreign_keys=[editor_id])
    restored_from = relationship("BlogRevision", remote_side=[id], foreign_keys=[restored_from_revision_id])

    __table_args__ = (
        UniqueConstraint("blog_id", "revision_number", name="uq_blog_revisions_number"),
        Index("ix_blog_revisions_company_blog", "company_id", "blog_id"),
        Index("ix_blog_revisions_blog_revnum", "blog_id", "revision_number"),
    )

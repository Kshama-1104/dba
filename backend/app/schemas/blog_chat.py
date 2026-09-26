"""Pydantic schemas for Phase 8 — Editor Chat & Blog Revisions."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.blog import BlogDetailResponse


class BlogChatRequest(BaseModel):
    """Editor instruction request payload."""
    message: str = Field(..., min_length=1, max_length=10000, description="Editor revision prompt / instruction")
    base_revision_id: int = Field(..., description="The revision ID this edit is based upon (for concurrency control)")
    client_message_id: Optional[str] = Field(None, max_length=64, description="Unique client message ID for idempotency")


class BlogChatMessageResponse(BaseModel):
    """Single chat message in the thread."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: int
    sender_type: str
    sender_id: Optional[int] = None
    message_type: str
    content: str
    client_message_id: Optional[str] = None
    message_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class BlogChatThreadResponse(BaseModel):
    """Conversation thread metadata and optionally recent messages."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    blog_id: int
    editor_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    messages: List[BlogChatMessageResponse] = Field(default_factory=list)


class BlogRevisionSummaryResponse(BaseModel):
    """Lightweight summary of a blog revision."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    blog_id: int
    revision_number: int
    revision_summary: str
    editor_id: Optional[int] = None
    seo_title: Optional[str] = None
    primary_keyword: Optional[str] = None
    restored_from_revision_id: Optional[int] = None
    created_at: datetime


class BlogRevisionDetailResponse(BlogRevisionSummaryResponse):
    """Full detail of a blog revision including content and validation report."""
    thread_id: Optional[int] = None
    message_id: Optional[int] = None
    content_json: Dict[str, Any]
    content_markdown: str
    meta_description: Optional[str] = None
    validation_report: Optional[Dict[str, Any]] = None


class BlogRestoreRequest(BaseModel):
    """Optional payload when restoring a revision."""
    restore_summary: Optional[str] = Field(None, max_length=500, description="Optional custom summary for the restore operation")


class BlogChatResponse(BaseModel):
    """Response returned after processing an editor chat message."""
    model_config = ConfigDict(from_attributes=True)

    thread_id: int
    user_message: BlogChatMessageResponse
    assistant_message: BlogChatMessageResponse
    revision: Optional[BlogRevisionSummaryResponse] = None
    blog: Optional[BlogDetailResponse] = None
    validation_report: Optional[Dict[str, Any]] = None

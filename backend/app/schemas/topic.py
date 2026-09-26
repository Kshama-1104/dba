from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TopicStatus(str, Enum):
    SUGGESTED = "suggested"
    SELECTED = "selected"
    REJECTED = "rejected"
    USED = "used"
    EXPIRED = "expired"


class TopicCandidateCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    angle: Optional[str] = None
    rationale: Optional[str] = None
    target_audience: Optional[str] = None
    source_context: Optional[str] = None
    primary_keyword: Optional[str] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Title cannot be empty or whitespace only.")
        return s


class TopicGenerateRequest(BaseModel):
    focus_theme: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional editorial focus, campaign theme, or direction",
    )
    target_keyword: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional target focus keyword",
    )


class TopicCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    title: str
    angle: Optional[str] = None
    rationale: Optional[str] = None
    target_audience: Optional[str] = None
    source_context: Optional[str] = None
    primary_keyword: Optional[str] = None
    relevance_score: Optional[float] = None
    freshness_score: Optional[float] = None
    status: TopicStatus
    created_at: datetime
    updated_at: datetime

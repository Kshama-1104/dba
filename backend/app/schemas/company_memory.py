import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.models.company_memory import (
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
    MemoryType,
)

# Common sensitive patterns to reject from memory storage
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(bearer\s+ey[a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
    re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*\S+"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)(otp|captcha_code|2fa[_-]?secret|totp[_-]?secret)\s*[:=]\s*\S+"),
]


def validate_no_sensitive_data(content: str) -> str:
    """
    Validate that content does not contain raw credentials, tokens, or private keys.
    """
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(content):
            raise ValueError(
                "Memory content contains sensitive credentials, tokens, or secrets and cannot be persisted."
            )
    return content


class CompanyMemoryCreate(BaseModel):
    memory_type: MemoryType = Field(..., description="SEMANTIC, EPISODIC, or PROCEDURAL")
    content: str = Field(..., min_length=3, max_length=5000, description="Durable memory content")
    source: MemorySource = Field(default=MemorySource.EXPLICIT_USER, description="Provenance source")
    confidence: MemoryConfidence = Field(default=MemoryConfidence.HIGH, description="HIGH, MEDIUM, or LOW")
    importance: int = Field(default=3, ge=1, le=5, description="Importance scale from 1 (low) to 5 (critical)")
    status: MemoryStatus = Field(default=MemoryStatus.ACTIVE, description="CANDIDATE or ACTIVE")
    metadata_payload: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured metadata")

    @field_validator("content")
    @classmethod
    def check_content_safety(cls, value: str) -> str:
        return validate_no_sensitive_data(value)


class CompanyMemoryUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=3, max_length=5000)
    memory_type: Optional[MemoryType] = None
    confidence: Optional[MemoryConfidence] = None
    importance: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[MemoryStatus] = None
    metadata_payload: Optional[Dict[str, Any]] = None

    @field_validator("content")
    @classmethod
    def check_content_safety(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            return validate_no_sensitive_data(value)
        return value


class CompanyMemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    memory_type: MemoryType
    content: str
    source: MemorySource
    confidence: MemoryConfidence
    importance: int
    status: MemoryStatus
    superseded_by_id: Optional[int] = None
    metadata_payload: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    last_accessed_at: Optional[datetime] = None


class CompanyMemoryListResponse(BaseModel):
    total: int
    memories: List[CompanyMemoryResponse]


class MemoryRetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Search query or topic context")
    memory_type: Optional[MemoryType] = Field(default=None, description="Optional filter by memory category")
    top_k: int = Field(default=5, ge=1, le=50, description="Max memory items to retrieve")
    include_candidates: bool = Field(default=False, description="Whether to include CANDIDATE memories")


class RetrievedMemoryItem(BaseModel):
    id: int
    company_id: int
    memory_type: MemoryType
    content: str
    source: MemorySource
    confidence: MemoryConfidence
    importance: int
    status: MemoryStatus
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")


class MemoryRetrievalResponse(BaseModel):
    query: str
    total_results: int
    memories: List[RetrievedMemoryItem]


class MemoryConflictResolutionResponse(BaseModel):
    company_id: int
    conflicts_detected: int
    structured_profile_precedence_applied: bool
    summary: str
    active_memory_count: int

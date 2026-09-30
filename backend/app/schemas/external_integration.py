from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IntegrationPlatform(str, Enum):
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    TWITTER_X = "twitter_x"
    GENERIC_WEB = "generic_web"


class IntegrationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"
    DISCONNECTED = "DISCONNECTED"


class SyncStatus(str, Enum):
    IDLE = "IDLE"
    SYNCING = "SYNCING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class IntegrationConnectRequest(BaseModel):
    platform: IntegrationPlatform
    name: str = Field(..., min_length=1, max_length=255)
    api_key: Optional[str] = Field(None, max_length=1000)
    access_token: Optional[str] = Field(None, max_length=4000)
    account_id: Optional[str] = Field(None, max_length=255)
    metadata_payload: Optional[Dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Integration name cannot be whitespace only.")
        return s

    def get_credential_dict(self) -> Dict[str, str]:
        creds = {}
        if self.api_key and self.api_key.strip():
            creds["api_key"] = self.api_key.strip()
        if self.access_token and self.access_token.strip():
            creds["access_token"] = self.access_token.strip()
        if self.account_id and self.account_id.strip():
            creds["account_id"] = self.account_id.strip()
        if not creds:
            raise ValueError("At least one credential field (api_key, access_token, or account_id) must be provided.")
        return creds


class IntegrationUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[IntegrationStatus] = None
    metadata_payload: Optional[Dict[str, Any]] = None


class IntegrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    platform: str
    name: str
    status: str
    sync_status: str
    last_synced_at: Optional[datetime] = None
    sync_error: Optional[str] = None
    metadata_payload: Optional[Dict[str, Any]] = None
    masked_credential: str = "********"
    created_at: datetime
    updated_at: datetime


class InsightItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    integration_id: int
    platform: str
    external_id: str
    source_url: Optional[str] = None
    author: Optional[str] = None
    content: str
    content_hash: str
    published_at: Optional[datetime] = None
    fetched_at: datetime
    freshness_score: float
    metadata_payload: Optional[Dict[str, Any]] = None
    created_at: datetime


class InsightRetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(5, ge=1, le=50)
    platform: Optional[IntegrationPlatform] = None
    min_similarity: float = Field(0.0, ge=0.0, le=1.0)


class RetrievedInsightItem(BaseModel):
    id: int
    company_id: int
    integration_id: int
    platform: str
    external_id: str
    source_url: Optional[str] = None
    author: Optional[str] = None
    content: str
    published_at: Optional[datetime] = None
    similarity_score: float
    freshness_score: float
    final_score: float


class SyncResultResponse(BaseModel):
    integration_id: int
    company_id: int
    platform: str
    fetched_count: int
    created_count: int
    updated_count: int
    skipped_count: int
    sync_status: str
    error: Optional[str] = None

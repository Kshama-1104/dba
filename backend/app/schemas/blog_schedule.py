from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ScheduleCreateRequest(BaseModel):
    local_scheduled_time: datetime = Field(..., description="Target local wall-clock time (e.g. 2026-10-15T09:30:00)")
    timezone: str = Field(..., description="Canonical IANA timezone identifier (e.g. Asia/Kolkata, America/New_York)")
    target_revision_id: Optional[int] = Field(None, description="Optional target revision ID; if provided, must match approved review revision")


class RescheduleRequest(BaseModel):
    local_scheduled_time: datetime = Field(..., description="New target local wall-clock time")
    timezone: Optional[str] = Field(None, description="Optional new canonical IANA timezone identifier")


class ScheduleCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Optional reason for cancellation")


class BlogScheduleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    company_id: int
    event_type: str
    actor_user_id: Optional[int] = None
    previous_scheduled_at_utc: Optional[datetime] = None
    new_scheduled_at_utc: Optional[datetime] = None
    previous_local_scheduled_time: Optional[datetime] = None
    new_local_scheduled_time: Optional[datetime] = None
    previous_timezone: Optional[str] = None
    new_timezone: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime


class BlogPublicationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    company_id: int
    blog_id: int
    revision_id: int
    attempt_number: int
    idempotency_key: str
    status: str
    worker_id: Optional[str] = None
    was_delayed: bool
    started_at: Optional[datetime] = None
    lease_until: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_details: Optional[str] = None
    external_reference: Optional[str] = None
    created_at: datetime


class BlogScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    blog_id: int
    target_revision_id: int
    scheduled_at_utc: datetime
    local_scheduled_time: datetime
    timezone: str
    status: str
    attempt_count: int
    max_attempts: int
    reschedule_count: int
    failure_code: Optional[str] = None
    last_error: Optional[str] = None
    created_by_user_id: int
    cancelled_by_user_id: Optional[int] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class BlogScheduleDetailResponse(BlogScheduleResponse):
    events: List[BlogScheduleEventResponse] = []
    publication_jobs: List[BlogPublicationJobResponse] = []

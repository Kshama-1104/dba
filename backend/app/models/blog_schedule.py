from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class ScheduleStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PublicationJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ScheduleEventType(str, Enum):
    SCHEDULE_CREATED = "SCHEDULE_CREATED"
    SCHEDULE_TRIGGERED = "SCHEDULE_TRIGGERED"
    SCHEDULE_RESCHEDULED = "SCHEDULE_RESCHEDULED"
    SCHEDULE_CANCELLED = "SCHEDULE_CANCELLED"
    SCHEDULE_BACKOFF = "SCHEDULE_BACKOFF"
    SCHEDULE_SUCCEEDED = "SCHEDULE_SUCCEEDED"
    SCHEDULE_FAILED = "SCHEDULE_FAILED"


class BlogSchedule(Base):
    __tablename__ = "blog_schedules"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    blog_id = Column(Integer, ForeignKey("blogs.id", ondelete="CASCADE"), nullable=False, index=True)
    target_revision_id = Column(Integer, ForeignKey("blog_revisions.id", ondelete="RESTRICT"), nullable=False, index=True)
    scheduled_at_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    local_scheduled_time = Column(DateTime(timezone=False), nullable=False)
    timezone = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default=ScheduleStatus.SCHEDULED.value, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    reschedule_count = Column(Integer, nullable=False, default=0)
    failure_code = Column(String(64), nullable=True)
    last_error = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cancelled_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    company = relationship("Company")
    blog = relationship("Blog")
    target_revision = relationship("BlogRevision")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_user_id])
    events = relationship("BlogScheduleEvent", back_populates="schedule", cascade="all, delete-orphan", order_by="BlogScheduleEvent.created_at.asc()")
    publication_jobs = relationship("BlogPublicationJob", back_populates="schedule", cascade="all, delete-orphan", order_by="BlogPublicationJob.attempt_number.asc()")

    __table_args__ = (
        # Partial unique index: exactly one active schedule per blog
        Index(
            "uq_blog_active_schedule",
            "blog_id",
            unique=True,
            postgresql_where=(Column("status").in_([ScheduleStatus.SCHEDULED.value, ScheduleStatus.QUEUED.value, ScheduleStatus.RUNNING.value])),
        ),
        # Due schedule polling index
        Index(
            "ix_blog_schedules_due_poll",
            "scheduled_at_utc",
            postgresql_where=(Column("status") == ScheduleStatus.SCHEDULED.value),
        ),
    )


class BlogScheduleEvent(Base):
    __tablename__ = "blog_schedule_events"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("blog_schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    previous_scheduled_at_utc = Column(DateTime(timezone=True), nullable=True)
    new_scheduled_at_utc = Column(DateTime(timezone=True), nullable=True)
    previous_local_scheduled_time = Column(DateTime(timezone=False), nullable=True)
    new_local_scheduled_time = Column(DateTime(timezone=False), nullable=True)
    previous_timezone = Column(String(64), nullable=True)
    new_timezone = Column(String(64), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    schedule = relationship("BlogSchedule", back_populates="events")
    company = relationship("Company")
    actor = relationship("User", foreign_keys=[actor_user_id])


class BlogPublicationJob(Base):
    __tablename__ = "blog_publication_jobs"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("blog_schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    blog_id = Column(Integer, ForeignKey("blogs.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_id = Column(Integer, ForeignKey("blog_revisions.id", ondelete="RESTRICT"), nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(32), nullable=False, default=PublicationJobStatus.QUEUED.value, index=True)
    worker_id = Column(String(128), nullable=True)
    was_delayed = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_details = Column(Text, nullable=True)
    external_reference = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    schedule = relationship("BlogSchedule", back_populates="publication_jobs")
    company = relationship("Company")
    blog = relationship("Blog")
    revision = relationship("BlogRevision")

    __table_args__ = (
        # Partial unique index: exactly one active publication job per schedule
        Index(
            "uq_pub_job_one_active_per_schedule",
            "schedule_id",
            unique=True,
            postgresql_where=(Column("status").in_([PublicationJobStatus.QUEUED.value, PublicationJobStatus.RUNNING.value])),
        ),
        # Lease recovery index
        Index(
            "ix_blog_pub_jobs_lease_recovery",
            "lease_until",
            postgresql_where=(Column("status") == PublicationJobStatus.RUNNING.value),
        ),
    )

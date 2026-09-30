import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os
import re
import socket
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.models.blog import Blog, BlogStatus
from backend.app.models.blog_chat import BlogRevision
from backend.app.models.blog_review import BlogReview
from backend.app.models.blog_schedule import (
    BlogPublicationJob,
    BlogSchedule,
    BlogScheduleEvent,
    PublicationJobStatus,
    ScheduleEventType,
    ScheduleStatus,
)
from backend.app.services.publication_contract import (
    BasePublicationProvider,
    PublicationContract,
    PublicationResult,
)

logger = logging.getLogger(__name__)


def sanitize_error(msg: Optional[str]) -> Optional[str]:
    """Sanitize error message to ensure no secrets, keys, or passwords leak."""
    if not msg:
        return msg
    # Redact common credential patterns (bearer tokens, passwords, api keys, db urls)
    sanitized = re.sub(r'(bearer\s+)[A-Za-z0-9_\-\.]+', r'\1[REDACTED]', msg, flags=re.IGNORECASE)
    sanitized = re.sub(r'(password=)[^\s&]+', r'\1[REDACTED]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'(api[_\-]?key=)[^\s&]+', r'\1[REDACTED]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'(postgresql:\/\/[^:]+:)[^@]+(@)', r'\1[REDACTED]\2', sanitized, flags=re.IGNORECASE)
    return sanitized[:1000]


class SchedulerWorker:
    """Production-grade scheduler worker utilizing PostgreSQL ACID row locking."""

    def __init__(self, worker_id: Optional[str] = None, poll_interval: float = 15.0):
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
        self.poll_interval = poll_interval
        self._running = False

    def claim_due_schedules(self, db: Session, batch_size: int = 10) -> List[int]:
        """TRANSACTION A: Atomically claim due schedules using SELECT FOR UPDATE SKIP LOCKED."""
        now_utc = datetime.now(timezone.utc)

        # 1. Fetch due schedules with row locking
        due_schedules = (
            db.query(BlogSchedule)
            .filter(
                BlogSchedule.status == ScheduleStatus.SCHEDULED.value,
                BlogSchedule.scheduled_at_utc <= now_utc,
            )
            .order_by(BlogSchedule.scheduled_at_utc.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
            .all()
        )

        claimed_ids = []

        for sched in due_schedules:
            # Check 2-hour outage threshold
            lateness = (now_utc - sched.scheduled_at_utc).total_seconds()
            if lateness > 7200:  # > 2 hours outage
                sched.status = ScheduleStatus.FAILED.value
                sched.failure_code = "SCHEDULE_EXPIRED_DURING_OUTAGE"
                sched.last_error = "Scheduler recovery threshold (2 hours) exceeded"
                sched.updated_at = now_utc

                event = BlogScheduleEvent(
                    schedule_id=sched.id,
                    company_id=sched.company_id,
                    event_type=ScheduleEventType.SCHEDULE_FAILED.value,
                    reason="SCHEDULE_EXPIRED_DURING_OUTAGE",
                )
                db.add(event)
                continue

            # Verify Blog approval and revision binding integrity using Phase 9 persisted source of truth
            blog = (
                db.query(Blog)
                .filter(Blog.id == sched.blog_id, Blog.company_id == sched.company_id)
                .first()
            )
            latest_approved_review = (
                db.query(BlogReview)
                .filter(
                    BlogReview.blog_id == sched.blog_id,
                    BlogReview.company_id == sched.company_id,
                    BlogReview.status == "approved",
                )
                .order_by(BlogReview.decided_at.desc(), BlogReview.id.desc())
                .first()
            )
            revision = (
                db.query(BlogRevision)
                .filter(
                    BlogRevision.id == sched.target_revision_id,
                    BlogRevision.blog_id == sched.blog_id,
                    BlogRevision.company_id == sched.company_id,
                )
                .first()
            )

            is_valid = (
                blog is not None
                and blog.status == BlogStatus.APPROVED
                and latest_approved_review is not None
                and latest_approved_review.submitted_revision_id is not None
                and latest_approved_review.submitted_revision_id == sched.target_revision_id
                and revision is not None
            )

            if not is_valid:
                sched.status = ScheduleStatus.FAILED.value
                sched.failure_code = "INVALID_BLOG_STATE"
                sched.last_error = "Blog is no longer in APPROVED status or revision mismatch"
                sched.updated_at = now_utc

                event = BlogScheduleEvent(
                    schedule_id=sched.id,
                    company_id=sched.company_id,
                    event_type=ScheduleEventType.SCHEDULE_FAILED.value,
                    reason="INVALID_BLOG_STATE",
                )
                db.add(event)
                continue

            # Check attempt limit
            attempt_number = sched.attempt_count + 1
            if attempt_number > sched.max_attempts:
                sched.status = ScheduleStatus.FAILED.value
                sched.failure_code = "MAX_ATTEMPTS_EXCEEDED"
                sched.last_error = "Maximum attempts exceeded"
                sched.updated_at = now_utc

                event = BlogScheduleEvent(
                    schedule_id=sched.id,
                    company_id=sched.company_id,
                    event_type=ScheduleEventType.SCHEDULE_FAILED.value,
                    reason="MAX_ATTEMPTS_EXCEEDED",
                )
                db.add(event)
                continue

            # Transition BlogSchedule: SCHEDULED -> QUEUED
            sched.status = ScheduleStatus.QUEUED.value
            sched.updated_at = now_utc

            # Create BlogPublicationJob: QUEUED
            attempt_idempotency_key = f"pub_schedule_{sched.id}_rev_{sched.target_revision_id}_attempt_{attempt_number}"
            job = BlogPublicationJob(
                schedule_id=sched.id,
                company_id=sched.company_id,
                blog_id=sched.blog_id,
                revision_id=sched.target_revision_id,
                attempt_number=attempt_number,
                idempotency_key=attempt_idempotency_key,
                status=PublicationJobStatus.QUEUED.value,
                was_delayed=(lateness > 60),
            )
            db.add(job)

            # Record SCHEDULE_TRIGGERED event
            event = BlogScheduleEvent(
                schedule_id=sched.id,
                company_id=sched.company_id,
                event_type=ScheduleEventType.SCHEDULE_TRIGGERED.value,
            )
            db.add(event)
            claimed_ids.append(sched.id)

        db.commit()
        return claimed_ids

    def start_execution(self, db: Session, schedule_id: int) -> Optional[int]:
        """TRANSACTION B: Transition both Schedule and PublicationJob from QUEUED -> RUNNING."""
        # 1. Lock queued publication job
        job = (
            db.query(BlogPublicationJob)
            .filter(
                BlogPublicationJob.schedule_id == schedule_id,
                BlogPublicationJob.status == PublicationJobStatus.QUEUED.value,
            )
            .with_for_update()
            .first()
        )

        # 2. Lock parent schedule
        sched = (
            db.query(BlogSchedule)
            .filter(BlogSchedule.id == schedule_id)
            .with_for_update()
            .first()
        )

        if not job or not sched:
            db.rollback()
            return None

        # Check if schedule was cancelled while queued
        if sched.status == ScheduleStatus.CANCELLED.value:
            job.status = PublicationJobStatus.FAILED.value
            job.error_details = "CANCELLED_BEFORE_EXECUTION"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return None

        if sched.status != ScheduleStatus.QUEUED.value or job.status != PublicationJobStatus.QUEUED.value:
            db.rollback()
            return None

        # Attempt count bounds check
        if sched.attempt_count + 1 > sched.max_attempts:
            sched.status = ScheduleStatus.FAILED.value
            sched.failure_code = "MAX_ATTEMPTS_EXCEEDED"
            job.status = PublicationJobStatus.FAILED.value
            job.error_details = "MAX_ATTEMPTS_EXCEEDED"
            db.commit()
            return None

        now_utc = datetime.now(timezone.utc)

        # Set Schedule: RUNNING and increment started attempt count
        sched.status = ScheduleStatus.RUNNING.value
        sched.attempt_count += 1
        sched.updated_at = now_utc

        # Set Job: RUNNING with worker lease
        job.status = PublicationJobStatus.RUNNING.value
        job.worker_id = self.worker_id
        job.started_at = now_utc
        job.lease_until = now_utc + timedelta(minutes=5)

        db.commit()
        return job.id

    async def execute_publication(
        self,
        db: Session,
        job_id: int,
        publisher: BasePublicationProvider,
    ) -> PublicationResult:
        """PHASE C: Execute Phase 11 publication contract outside database transactions."""
        job = db.query(BlogPublicationJob).filter(BlogPublicationJob.id == job_id).first()
        if not job:
            return PublicationResult(success=False, error_message="Job not found")

        revision = db.query(BlogRevision).filter(BlogRevision.id == job.revision_id).first()
        if not revision:
            return PublicationResult(success=False, error_message="Pinned revision missing")

        blog = db.query(Blog).filter(Blog.id == job.blog_id).first()
        contract_title = (revision.seo_title if revision and revision.seo_title else None) or (blog.title if blog and blog.title else "")

        # Stable logical publication idempotency key across all retries
        logical_key = f"pub_schedule_{job.schedule_id}_rev_{job.revision_id}"

        contract = PublicationContract(
            job_id=job.id,
            schedule_id=job.schedule_id,
            company_id=job.company_id,
            blog_id=job.blog_id,
            revision_id=job.revision_id,
            title=contract_title,
            content_markdown=revision.content_markdown or "",
            content_json=revision.content_json or {},
            attempt_number=job.attempt_number,
            publication_idempotency_key=logical_key,
        )

        try:
            return await publisher.publish(contract)
        except Exception as e:
            logger.error(f"Phase 11 publication execution error: {e}")
            return PublicationResult(
                success=False,
                is_transient_error=True,
                error_code="PUBLISHER_INVOCATION_ERROR",
                error_message=str(e),
            )

    def record_result(self, db: Session, job_id: int, result: PublicationResult) -> None:
        """TRANSACTION C: Record publication outcome into Job and Schedule with stale worker check."""
        job = (
            db.query(BlogPublicationJob)
            .filter(
                BlogPublicationJob.id == job_id,
                BlogPublicationJob.worker_id == self.worker_id,
                BlogPublicationJob.status == PublicationJobStatus.RUNNING.value,
            )
            .with_for_update()
            .first()
        )
        if not job:
            db.rollback()
            logger.warning(f"Discarding stale or non-existent job execution result: {job_id}")
            return

        sched = (
            db.query(BlogSchedule)
            .filter(BlogSchedule.id == job.schedule_id)
            .with_for_update()
            .first()
        )
        if not sched:
            db.rollback()
            return

        now_utc = datetime.now(timezone.utc)
        if job.lease_until and job.lease_until < now_utc:
            # Lease expired! Discard write to protect against stale worker updates
            db.rollback()
            logger.warning(f"Discarding stale result from worker {self.worker_id}: lease expired")
            return

        sanitized_err = sanitize_error(result.error_message)

        if result.success:
            job.status = PublicationJobStatus.SUCCEEDED.value
            job.completed_at = now_utc
            job.external_reference = result.external_reference

            sched.status = ScheduleStatus.SUCCEEDED.value
            sched.updated_at = now_utc

            event = BlogScheduleEvent(
                schedule_id=sched.id,
                company_id=sched.company_id,
                event_type=ScheduleEventType.SCHEDULE_SUCCEEDED.value,
            )
            db.add(event)

        elif result.is_transient_error:
            job.status = PublicationJobStatus.FAILED.value
            job.completed_at = now_utc
            job.error_details = sanitized_err

            next_attempt = job.attempt_number + 1
            if next_attempt <= sched.max_attempts:
                # Calculate backoff
                backoff_secs = 60 if job.attempt_number == 1 else 180
                sched.status = ScheduleStatus.SCHEDULED.value
                sched.scheduled_at_utc = now_utc + timedelta(seconds=backoff_secs)
                sched.updated_at = now_utc

                event = BlogScheduleEvent(
                    schedule_id=sched.id,
                    company_id=sched.company_id,
                    event_type=ScheduleEventType.SCHEDULE_BACKOFF.value,
                    new_scheduled_at_utc=sched.scheduled_at_utc,
                    reason=f"Transient failure: {sanitized_err}",
                )
                db.add(event)
            else:
                sched.status = ScheduleStatus.FAILED.value
                sched.failure_code = "MAX_ATTEMPTS_EXCEEDED"
                sched.last_error = sanitized_err
                sched.updated_at = now_utc

                event = BlogScheduleEvent(
                    schedule_id=sched.id,
                    company_id=sched.company_id,
                    event_type=ScheduleEventType.SCHEDULE_FAILED.value,
                    reason="MAX_ATTEMPTS_EXCEEDED",
                )
                db.add(event)

        else:
            # Permanent failure
            job.status = PublicationJobStatus.FAILED.value
            job.completed_at = now_utc
            job.error_details = sanitized_err

            sched.status = ScheduleStatus.FAILED.value
            sched.failure_code = result.error_code or "PERMANENT_PUBLICATION_FAILURE"
            sched.last_error = sanitized_err
            sched.updated_at = now_utc

            event = BlogScheduleEvent(
                schedule_id=sched.id,
                company_id=sched.company_id,
                event_type=ScheduleEventType.SCHEDULE_FAILED.value,
                reason=result.error_code or "PERMANENT_PUBLICATION_FAILURE",
            )
            db.add(event)

        db.commit()

    def reclaim_expired_leases(self, db: Session) -> int:
        """Reclaim abandoned publication jobs whose worker lease has expired."""
        now_utc = datetime.now(timezone.utc)

        expired_jobs = (
            db.query(BlogPublicationJob)
            .filter(
                BlogPublicationJob.status == PublicationJobStatus.RUNNING.value,
                BlogPublicationJob.lease_until < now_utc,
            )
            .with_for_update(skip_locked=True)
            .all()
        )

        reclaimed_count = 0
        for job in expired_jobs:
            job.status = PublicationJobStatus.FAILED.value
            job.completed_at = now_utc
            job.error_details = "WORKER_CRASHED_LEASE_EXPIRED"

            sched = (
                db.query(BlogSchedule)
                .filter(BlogSchedule.id == job.schedule_id)
                .with_for_update()
                .first()
            )
            if sched:
                next_attempt = job.attempt_number + 1
                if next_attempt <= sched.max_attempts:
                    sched.status = ScheduleStatus.SCHEDULED.value
                    sched.scheduled_at_utc = now_utc + timedelta(seconds=60)
                    sched.updated_at = now_utc

                    event = BlogScheduleEvent(
                        schedule_id=sched.id,
                        company_id=sched.company_id,
                        event_type=ScheduleEventType.SCHEDULE_BACKOFF.value,
                        new_scheduled_at_utc=sched.scheduled_at_utc,
                        reason="WORKER_CRASHED_LEASE_EXPIRED",
                    )
                    db.add(event)
                else:
                    sched.status = ScheduleStatus.FAILED.value
                    sched.failure_code = "WORKER_CRASH_MAX_ATTEMPTS_EXCEEDED"
                    sched.last_error = "WORKER_CRASHED_LEASE_EXPIRED"
                    sched.updated_at = now_utc

                    event = BlogScheduleEvent(
                        schedule_id=sched.id,
                        company_id=sched.company_id,
                        event_type=ScheduleEventType.SCHEDULE_FAILED.value,
                        reason="WORKER_CRASH_MAX_ATTEMPTS_EXCEEDED",
                    )
                    db.add(event)

            reclaimed_count += 1

        db.commit()
        return reclaimed_count

    async def process_one_schedule(
        self,
        db: Session,
        schedule_id: int,
        publisher: BasePublicationProvider,
    ) -> bool:
        """Helper to run Start (Tx B) -> External (Phase C) -> Result (Tx C) for a claimed schedule."""
        job_id = self.start_execution(db, schedule_id)
        if not job_id:
            return False

        result = await self.execute_publication(db, job_id, publisher)
        self.record_result(db, job_id, result)
        return result.success

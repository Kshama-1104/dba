from datetime import datetime, timedelta, timezone
from typing import List, Optional
import zoneinfo

from fastapi import HTTPException, status
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
from backend.app.models.user import User
from backend.app.schemas.blog_schedule import (
    RescheduleRequest,
    ScheduleCancelRequest,
    ScheduleCreateRequest,
)


class BlogScheduleService:
    @staticmethod
    def validate_and_localize_schedule_time(local_time: datetime, tz_name: str) -> datetime:
        """Validate IANA timezone, detect DST gap/ambiguity, enforce 60s lead time, and return UTC instant."""
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid IANA timezone identifier",
            )

        # Ensure local_time is naive for timezone localization
        if local_time.tzinfo is not None:
            local_time = local_time.replace(tzinfo=None)

        # 1. Nonexistent local time check (DST spring-forward gap)
        candidate_utc = local_time.replace(tzinfo=tz).astimezone(timezone.utc)
        roundtrip_local = candidate_utc.astimezone(tz).replace(tzinfo=None)
        if roundtrip_local != local_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Requested local time does not exist in the selected timezone due to daylight saving spring-forward.",
            )

        # 2. Ambiguous local time check (DST fallback gap)
        dt_fold0 = local_time.replace(fold=0, tzinfo=tz)
        dt_fold1 = local_time.replace(fold=1, tzinfo=tz)
        if dt_fold0.utcoffset() != dt_fold1.utcoffset():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ambiguous local time during daylight saving fallback. Please specify an unambiguous time.",
            )

        # 3. Minimum scheduling lead time (60 seconds in the future)
        now_utc = datetime.now(timezone.utc)
        if candidate_utc <= now_utc + timedelta(seconds=60):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Scheduled time must be at least 60 seconds in the future",
            )

        return candidate_utc

    @staticmethod
    def create_schedule(
        db: Session,
        blog_id: int,
        current_user: User,
        request: ScheduleCreateRequest,
    ) -> BlogSchedule:
        """Create a new publication schedule for an approved blog revision."""
        # 1. Validate time & timezone
        scheduled_at_utc = BlogScheduleService.validate_and_localize_schedule_time(
            request.local_scheduled_time,
            request.timezone,
        )

        # 2. Lock parent Blog row to prevent concurrent review state changes
        blog = (
            db.query(Blog)
            .filter(Blog.id == blog_id, Blog.company_id == current_user.company_id)
            .with_for_update()
            .first()
        )
        if not blog:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found")

        # 3. Check blog approval state
        if blog.status != BlogStatus.APPROVED:
            status_val = blog.status.value if hasattr(blog.status, "value") else str(blog.status)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Blog must be in APPROVED status to be scheduled. Current status: {status_val}",
            )

        # 4. Verify approved review exists and has submitted_revision_id
        latest_approved_review = (
            db.query(BlogReview)
            .filter(
                BlogReview.blog_id == blog.id,
                BlogReview.company_id == current_user.company_id,
                BlogReview.status == "approved",
            )
            .order_by(BlogReview.decided_at.desc(), BlogReview.id.desc())
            .first()
        )
        if not latest_approved_review or not latest_approved_review.submitted_revision_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No approved review found for this blog",
            )

        approved_revision_id = latest_approved_review.submitted_revision_id

        # If client explicitly passed target_revision_id, verify it matches approved revision
        if hasattr(request, "target_revision_id") and request.target_revision_id is not None:
            if request.target_revision_id != approved_revision_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Current blog revision does not match approved review revision",
                )

        # 5. Verify revision belongs to this blog and company
        target_revision = (
            db.query(BlogRevision)
            .filter(
                BlogRevision.id == approved_revision_id,
                BlogRevision.blog_id == blog.id,
                BlogRevision.company_id == current_user.company_id,
            )
            .first()
        )
        if not target_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Approved revision not found for blog",
            )

        # 6. Check for existing active schedule
        active_schedule = (
            db.query(BlogSchedule)
            .filter(
                BlogSchedule.blog_id == blog.id,
                BlogSchedule.status.in_([
                    ScheduleStatus.SCHEDULED.value,
                    ScheduleStatus.QUEUED.value,
                    ScheduleStatus.RUNNING.value,
                ]),
            )
            .first()
        )
        if active_schedule:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active schedule already exists for this blog",
            )

        # 7. Create BlogSchedule
        schedule = BlogSchedule(
            company_id=current_user.company_id,
            blog_id=blog.id,
            target_revision_id=target_revision.id,
            scheduled_at_utc=scheduled_at_utc,
            local_scheduled_time=request.local_scheduled_time.replace(tzinfo=None),
            timezone=request.timezone,
            status=ScheduleStatus.SCHEDULED.value,
            attempt_count=0,
            max_attempts=3,
            reschedule_count=0,
            created_by_user_id=current_user.id,
        )
        db.add(schedule)
        db.flush()

        # 8. Record SCHEDULE_CREATED event
        event = BlogScheduleEvent(
            schedule_id=schedule.id,
            company_id=current_user.company_id,
            event_type=ScheduleEventType.SCHEDULE_CREATED.value,
            actor_user_id=current_user.id,
            new_scheduled_at_utc=scheduled_at_utc,
            new_local_scheduled_time=schedule.local_scheduled_time,
            new_timezone=schedule.timezone,
        )
        db.add(event)
        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def reschedule(
        db: Session,
        schedule_id: int,
        current_user: User,
        request: RescheduleRequest,
    ) -> BlogSchedule:
        """Reschedule an existing SCHEDULED blog schedule."""
        schedule = (
            db.query(BlogSchedule)
            .filter(BlogSchedule.id == schedule_id, BlogSchedule.company_id == current_user.company_id)
            .with_for_update()
            .first()
        )
        if not schedule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

        if schedule.status != ScheduleStatus.SCHEDULED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reschedule a schedule in status '{schedule.status}'. Only SCHEDULED schedules can be rescheduled.",
            )

        tz_name = request.timezone or schedule.timezone
        new_scheduled_at_utc = BlogScheduleService.validate_and_localize_schedule_time(
            request.local_scheduled_time,
            tz_name,
        )

        # Record event
        event = BlogScheduleEvent(
            schedule_id=schedule.id,
            company_id=current_user.company_id,
            event_type=ScheduleEventType.SCHEDULE_RESCHEDULED.value,
            actor_user_id=current_user.id,
            previous_scheduled_at_utc=schedule.scheduled_at_utc,
            new_scheduled_at_utc=new_scheduled_at_utc,
            previous_local_scheduled_time=schedule.local_scheduled_time,
            new_local_scheduled_time=request.local_scheduled_time.replace(tzinfo=None),
            previous_timezone=schedule.timezone,
            new_timezone=tz_name,
        )
        db.add(event)

        schedule.scheduled_at_utc = new_scheduled_at_utc
        schedule.local_scheduled_time = request.local_scheduled_time.replace(tzinfo=None)
        schedule.timezone = tz_name
        schedule.reschedule_count += 1
        schedule.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def cancel_schedule(
        db: Session,
        schedule_id: int,
        current_user: User,
        request: ScheduleCancelRequest,
    ) -> BlogSchedule:
        """Cancel a schedule if in SCHEDULED or QUEUED state."""
        schedule = (
            db.query(BlogSchedule)
            .filter(BlogSchedule.id == schedule_id, BlogSchedule.company_id == current_user.company_id)
            .with_for_update()
            .first()
        )
        if not schedule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

        if schedule.status == ScheduleStatus.RUNNING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot cancel a schedule that is currently publishing",
            )

        if schedule.status in (
            ScheduleStatus.SUCCEEDED.value,
            ScheduleStatus.FAILED.value,
            ScheduleStatus.CANCELLED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel a schedule in terminal status '{schedule.status}'",
            )

        # If QUEUED, also cancel any queued publication job
        if schedule.status == ScheduleStatus.QUEUED.value:
            queued_job = (
                db.query(BlogPublicationJob)
                .filter(
                    BlogPublicationJob.schedule_id == schedule.id,
                    BlogPublicationJob.status == PublicationJobStatus.QUEUED.value,
                )
                .with_for_update()
                .first()
            )
            if queued_job:
                queued_job.status = PublicationJobStatus.FAILED.value
                queued_job.error_details = "CANCELLED_BEFORE_EXECUTION"
                queued_job.completed_at = datetime.now(timezone.utc)

        schedule.status = ScheduleStatus.CANCELLED.value
        schedule.cancelled_by_user_id = current_user.id
        schedule.cancelled_at = datetime.now(timezone.utc)
        schedule.updated_at = datetime.now(timezone.utc)

        event = BlogScheduleEvent(
            schedule_id=schedule.id,
            company_id=current_user.company_id,
            event_type=ScheduleEventType.SCHEDULE_CANCELLED.value,
            actor_user_id=current_user.id,
            reason=request.reason,
        )
        db.add(event)

        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def get_schedule(db: Session, schedule_id: int, current_user: User) -> BlogSchedule:
        """Fetch a specific schedule by ID with tenant isolation."""
        schedule = (
            db.query(BlogSchedule)
            .filter(BlogSchedule.id == schedule_id, BlogSchedule.company_id == current_user.company_id)
            .first()
        )
        if not schedule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
        return schedule

    @staticmethod
    def list_blog_schedules(db: Session, blog_id: int, current_user: User) -> List[BlogSchedule]:
        """List all schedules for a specific blog with tenant isolation."""
        blog = (
            db.query(Blog)
            .filter(Blog.id == blog_id, Blog.company_id == current_user.company_id)
            .first()
        )
        if not blog:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found")

        return (
            db.query(BlogSchedule)
            .filter(BlogSchedule.blog_id == blog_id, BlogSchedule.company_id == current_user.company_id)
            .order_by(BlogSchedule.created_at.desc())
            .all()
        )

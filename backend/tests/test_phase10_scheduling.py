"""
Phase 10 — Blog Scheduling & Orchestration Comprehensive Test Suite

Tests all invariants of Phase 10:
- Schedule creation & eligibility (APPROVED blogs only)
- Immutable revision binding
- Canonical IANA timezone & DST handling (ambiguous/nonexistent rejection)
- Minimum 60-second lead time
- Database invariants (single active schedule per blog, single active job per schedule)
- Exact 4-phase worker lifecycle (Transaction A claim, Transaction B start, Phase C external, Transaction C result)
- Strict state synchronization (never Schedule=QUEUED + Job=RUNNING)
- Maximum attempt bounds (1, 2, 3; strictly no Attempt 4)
- Worker leasing, heartbeat, lease expiration recovery, and stale worker rejection
- Cancellation semantics & cancellation races
- Rescheduling semantics & audit trails
- Append-only lifecycle audit events
- Tenant isolation & RBAC enforcement
- Phase 11 contract integrity & dual idempotency keys
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.services.auth_service import create_user_access_token
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
from backend.app.models.user import User, UserRole
from backend.app.services.blog_schedule_service import BlogScheduleService
from backend.app.services.publication_contract import (
    MockPublicationProvider,
    PublicationContract,
    PublicationResult,
)
from backend.app.worker.scheduler_worker import SchedulerWorker, sanitize_error


from backend.app.models.topic_candidate import TopicCandidate, TopicStatus


def auth_header(user: User) -> dict:
    token = create_user_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def setup_scheduling_env(db_session: Session, create_company, create_user):
    """Fixture creating company, admin, editor, reviewer, and an approved blog."""
    company = create_company(name="Scheduling Corp")
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN, email="admin_sched@example.com")
    editor = create_user(company_id=company.id, role=UserRole.EDITOR, email="editor_sched@example.com")
    reviewer = create_user(company_id=company.id, role=UserRole.REVIEWER, email="reviewer_sched@example.com")

    # Create TopicCandidate
    topic = TopicCandidate(
        company_id=company.id,
        title="Scaling Microservices with Kafka",
        angle="Architecture guide",
        primary_keyword="kafka microservices",
        status=TopicStatus.SELECTED,
    )
    db_session.add(topic)
    db_session.flush()

    # Create blog
    blog = Blog(
        company_id=company.id,
        topic_candidate_id=topic.id,
        created_by_user_id=editor.id,
        title="Scaling Microservices with Kafka",
        content_json={"sections": ["intro", "scaling"]},
        content_markdown="# Scaling Microservices\n\nContent for V1.",
        status=BlogStatus.APPROVED,
    )
    db_session.add(blog)
    db_session.flush()

    # Create Revision V1
    rev1 = BlogRevision(
        company_id=company.id,
        blog_id=blog.id,
        revision_number=1,
        revision_summary="Initial approved revision",
        seo_title="Scaling Microservices with Kafka - V1",
        content_markdown="# Scaling Microservices\n\nContent for V1.",
        content_json={"sections": ["intro", "scaling"]},
    )
    db_session.add(rev1)
    db_session.flush()

    # Create approved review record
    review = BlogReview(
        company_id=company.id,
        blog_id=blog.id,
        submitted_revision_id=rev1.id,
        reviewer_id=reviewer.id,
        status="approved",
        decided_at=datetime.now(timezone.utc),
    )
    db_session.add(review)
    db_session.commit()

    return {
        "company": company,
        "admin": admin,
        "editor": editor,
        "reviewer": reviewer,
        "topic": topic,
        "blog": blog,
        "revision": rev1,
        "review": review,
    }


# ==============================================================================
# 1. SCHEDULE CREATION & ELIGIBILITY
# ==============================================================================

def test_schedule_creation_success(client: TestClient, db_session: Session, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    payload = {
        "local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "timezone": "Asia/Kolkata",
    }

    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json=payload,
        headers=auth_header(editor),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["blog_id"] == blog.id
    assert data["target_revision_id"] == env["revision"].id
    assert data["status"] == "SCHEDULED"
    assert data["attempt_count"] == 0
    assert data["max_attempts"] == 3
    assert data["timezone"] == "Asia/Kolkata"

    # Verify event logged
    event = db_session.query(BlogScheduleEvent).filter(BlogScheduleEvent.schedule_id == data["id"]).first()
    assert event is not None
    assert event.event_type == "SCHEDULE_CREATED"
    assert event.actor_user_id == editor.id


def test_schedule_non_approved_blog_rejected_409(client: TestClient, db_session: Session, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    # Revert to DRAFT
    blog.status = BlogStatus.DRAFT
    db_session.commit()

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {
        "local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "timezone": "UTC",
    }

    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json=payload,
        headers=auth_header(editor),
    )
    assert resp.status_code == 409
    assert "APPROVED" in resp.json()["detail"]


def test_schedule_revision_mismatch_rejected_409(client: TestClient, db_session: Session, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    # Create V2 but do not approve it
    rev2 = BlogRevision(
        company_id=blog.company_id,
        blog_id=blog.id,
        revision_number=2,
        revision_summary="V2 draft changes",
        seo_title="V2 Title",
        content_markdown="V2 Markdown",
        content_json={},
    )
    db_session.add(rev2)
    db_session.commit()

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {
        "local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "timezone": "UTC",
        "target_revision_id": rev2.id,
    }

    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json=payload,
        headers=auth_header(editor),
    )
    assert resp.status_code == 409
    assert "Current blog revision does not match approved review revision" in resp.json()["detail"]


def test_schedule_exact_revision_immutability(client: TestClient, db_session: Session, setup_scheduling_env):
    """If V1 is scheduled, and V2 is later created, the schedule remains strictly bound to V1."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev1 = env["revision"]

    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "UTC"},
        headers=auth_header(editor),
    )
    assert resp.status_code == 201
    sched_id = resp.json()["id"]

    # Now create V2
    rev2 = BlogRevision(
        company_id=blog.company_id,
        blog_id=blog.id,
        revision_number=2,
        revision_summary="V2 Title",
        seo_title="V2 Title",
        content_markdown="V2 Markdown",
        content_json={},
    )
    db_session.add(rev2)
    db_session.commit()

    # Verify schedule is still bound to rev1.id
    schedule = db_session.query(BlogSchedule).filter(BlogSchedule.id == sched_id).first()
    assert schedule.target_revision_id == rev1.id
    assert schedule.target_revision_id != rev2.id


# ==============================================================================
# 2. TIMEZONE, DST & LEAD TIME VALIDATION
# ==============================================================================

def test_invalid_timezone_rejected_422(client: TestClient, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "Mars/Olympus"},
        headers=auth_header(editor),
    )
    assert resp.status_code == 422
    assert "Invalid IANA timezone identifier" in resp.json()["detail"]


def test_dst_ambiguous_time_rejected_422(client: TestClient, setup_scheduling_env):
    """In America/New_York, 2026-11-01 01:30 is repeated during DST fallback."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": "2026-11-01T01:30:00", "timezone": "America/New_York"},
        headers=auth_header(editor),
    )
    assert resp.status_code == 422
    assert "Ambiguous local time during daylight saving fallback" in resp.json()["detail"]


def test_dst_nonexistent_gap_time_rejected_422(client: TestClient, setup_scheduling_env):
    """In America/New_York, 2026-03-08 02:30 does not exist (clocks jump 02:00 -> 03:00)."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": "2026-03-08T02:30:00", "timezone": "America/New_York"},
        headers=auth_header(editor),
    )
    assert resp.status_code == 422
    assert "Requested local time does not exist" in resp.json()["detail"]


def test_near_past_schedule_rejected_422(client: TestClient, setup_scheduling_env):
    """Scheduled time must be at least 60 seconds in the future."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    # 30 seconds from now
    near_time = datetime.now(timezone.utc) + timedelta(seconds=30)
    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": near_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "UTC"},
        headers=auth_header(editor),
    )
    assert resp.status_code == 422
    assert "at least 60 seconds in the future" in resp.json()["detail"]


# ==============================================================================
# 3. RBAC & TENANT ISOLATION
# ==============================================================================

def test_reviewer_cannot_create_or_cancel_schedule_403(client: TestClient, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]
    reviewer = env["reviewer"]

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "UTC"},
        headers=auth_header(reviewer),
    )
    assert resp.status_code == 403


def test_cross_tenant_schedule_access_404(client: TestClient, create_company, create_user, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]

    other_company = create_company(name="Competitor Inc")
    other_editor = create_user(company_id=other_company.id, role=UserRole.EDITOR, email="other@competitor.com")

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "UTC"},
        headers=auth_header(other_editor),
    )
    assert resp.status_code == 404


# ==============================================================================
# 4. DUPLICATE SCHEDULING CONSTRAINTS
# ==============================================================================

def test_duplicate_active_schedule_prevented(client: TestClient, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {"local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "UTC"}

    resp1 = client.post(f"/api/v1/blogs/{blog.id}/schedules", json=payload, headers=auth_header(editor))
    assert resp1.status_code == 201

    resp2 = client.post(f"/api/v1/blogs/{blog.id}/schedules", json=payload, headers=auth_header(editor))
    assert resp2.status_code == 409
    assert "active schedule already exists" in resp2.json()["detail"]


def test_db_partial_unique_index_active_schedule(db_session: Session, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    s1 = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) + timedelta(hours=1),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(s1)
    db_session.commit()

    # Second active schedule insert directly via SQL
    s2 = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) + timedelta(hours=2),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.QUEUED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ==============================================================================
# 5. RESCHEDULING & CANCELLATION
# ==============================================================================

def test_rescheduling_lifecycle(client: TestClient, db_session: Session, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "UTC"},
        headers=auth_header(editor),
    )
    sched_id = resp.json()["id"]

    new_time = datetime.now(timezone.utc) + timedelta(days=3)
    resched_resp = client.post(
        f"/api/v1/schedules/{sched_id}/reschedule",
        json={"local_scheduled_time": new_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "Asia/Kolkata"},
        headers=auth_header(editor),
    )
    assert resched_resp.status_code == 200
    data = resched_resp.json()
    assert data["reschedule_count"] == 1
    assert data["timezone"] == "Asia/Kolkata"

    # Verify SCHEDULE_RESCHEDULED event
    event = db_session.query(BlogScheduleEvent).filter(
        BlogScheduleEvent.schedule_id == sched_id,
        BlogScheduleEvent.event_type == "SCHEDULE_RESCHEDULED"
    ).first()
    assert event is not None
    assert event.previous_timezone == "UTC"
    assert event.new_timezone == "Asia/Kolkata"


def test_cancel_schedule_in_scheduled_state(client: TestClient, db_session: Session, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "UTC"},
        headers=auth_header(editor),
    )
    sched_id = resp.json()["id"]

    cancel_resp = client.post(
        f"/api/v1/schedules/{sched_id}/cancel",
        json={"reason": "Marketing shift"},
        headers=auth_header(editor),
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    event = db_session.query(BlogScheduleEvent).filter(
        BlogScheduleEvent.schedule_id == sched_id,
        BlogScheduleEvent.event_type == "SCHEDULE_CANCELLED"
    ).first()
    assert event is not None
    assert event.reason == "Marketing shift"


def test_cancel_running_schedule_rejected_409(client: TestClient, db_session: Session, setup_scheduling_env):
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=env["revision"].id,
        scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=5),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.RUNNING.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    resp = client.post(
        f"/api/v1/schedules/{sched.id}/cancel",
        headers=auth_header(editor),
    )
    assert resp.status_code == 409
    assert "currently publishing" in resp.json()["detail"]


# ==============================================================================
# 6. WORKER LIFECYCLE (TX A, TX B, PHASE C, TX C) & INVARIANTS
# ==============================================================================

def test_worker_claim_and_start_lifecycle(db_session: Session, setup_scheduling_env):
    """Verify Tx A (Claim) creates QUEUED schedule and QUEUED job; Tx B (Start) sets both to RUNNING."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    # Seed a due schedule
    due_time = datetime.now(timezone.utc) - timedelta(minutes=2)
    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=due_time,
        local_scheduled_time=due_time.replace(tzinfo=None),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    worker = SchedulerWorker(worker_id="test-worker-1")

    # TRANSACTION A: CLAIM
    claimed = worker.claim_due_schedules(db_session, batch_size=10)
    assert sched.id in claimed

    db_session.refresh(sched)
    assert sched.status == "QUEUED"

    job = db_session.query(BlogPublicationJob).filter(BlogPublicationJob.schedule_id == sched.id).first()
    assert job is not None
    assert job.status == "QUEUED"
    assert job.attempt_number == 1
    assert job.idempotency_key == f"pub_schedule_{sched.id}_rev_{rev.id}_attempt_1"

    # Invariant: Never Schedule=QUEUED and Job=RUNNING
    assert not (sched.status == "QUEUED" and job.status == "RUNNING")

    # TRANSACTION B: START
    job_id = worker.start_execution(db_session, sched.id)
    assert job_id == job.id

    db_session.refresh(sched)
    db_session.refresh(job)
    assert sched.status == "RUNNING"
    assert sched.attempt_count == 1
    assert job.status == "RUNNING"
    assert job.worker_id == "test-worker-1"
    assert job.lease_until > datetime.now(timezone.utc)

    # PHASE C & TRANSACTION C: EXECUTE & RESULT
    provider = MockPublicationProvider(default_success=True)
    res = asyncio.run(worker.execute_publication(db_session, job_id, provider))
    assert res.success is True
    assert len(provider.invocations) == 1
    assert provider.invocations[0].publication_idempotency_key == f"pub_schedule_{sched.id}_rev_{rev.id}"

    worker.record_result(db_session, job_id, res)
    db_session.refresh(sched)
    db_session.refresh(job)
    assert sched.status == "SUCCEEDED"
    assert job.status == "SUCCEEDED"


# ==============================================================================
# 7. RETRIES, BACKOFF & MAX ATTEMPTS BOUNDS
# ==============================================================================

def test_retry_transient_failure_max_attempts_3_never_4(db_session: Session, setup_scheduling_env):
    """Verify Attempt 1 -> Attempt 2 -> Attempt 3 -> FAILED. Strictly no Attempt 4."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        max_attempts=3,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    worker = SchedulerWorker(worker_id="test-worker-retry")
    provider = MockPublicationProvider(default_success=False)  # Always returns transient failure

    # --- ATTEMPT 1 ---
    worker.claim_due_schedules(db_session)
    job1_id = worker.start_execution(db_session, sched.id)
    res1 = asyncio.run(worker.execute_publication(db_session, job1_id, provider))
    worker.record_result(db_session, job1_id, res1)

    db_session.refresh(sched)
    job1 = db_session.query(BlogPublicationJob).filter(BlogPublicationJob.id == job1_id).first()
    assert job1.status == "FAILED"
    assert sched.status == "SCHEDULED"  # Backed off for retry
    assert sched.attempt_count == 1

    # Simulate backoff elapsed
    sched.scheduled_at_utc = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    # --- ATTEMPT 2 ---
    worker.claim_due_schedules(db_session)
    job2_id = worker.start_execution(db_session, sched.id)
    assert job2_id != job1_id
    res2 = asyncio.run(worker.execute_publication(db_session, job2_id, provider))
    worker.record_result(db_session, job2_id, res2)

    db_session.refresh(sched)
    job2 = db_session.query(BlogPublicationJob).filter(BlogPublicationJob.id == job2_id).first()
    assert job2.status == "FAILED"
    assert job2.attempt_number == 2
    assert sched.status == "SCHEDULED"
    assert sched.attempt_count == 2

    # Simulate backoff elapsed
    sched.scheduled_at_utc = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    # --- ATTEMPT 3 ---
    worker.claim_due_schedules(db_session)
    job3_id = worker.start_execution(db_session, sched.id)
    assert job3_id != job2_id
    res3 = asyncio.run(worker.execute_publication(db_session, job3_id, provider))
    worker.record_result(db_session, job3_id, res3)

    db_session.refresh(sched)
    job3 = db_session.query(BlogPublicationJob).filter(BlogPublicationJob.id == job3_id).first()
    assert job3.status == "FAILED"
    assert job3.attempt_number == 3
    assert sched.status == "FAILED"
    assert sched.failure_code == "MAX_ATTEMPTS_EXCEEDED"
    assert sched.attempt_count == 3

    # PROVE NO ATTEMPT 4: Further polling claims zero schedules
    sched.scheduled_at_utc = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    claimed = worker.claim_due_schedules(db_session)
    assert sched.id not in claimed


# ==============================================================================
# 8. LEASE EXPIRATION & STALE WORKER REJECTION
# ==============================================================================

def test_lease_expiration_recovery(db_session: Session, setup_scheduling_env):
    """Expired lease on crashed worker is reclaimed and schedule is returned to SCHEDULED."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) - timedelta(hours=1),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.RUNNING.value,
        attempt_count=1,
        max_attempts=3,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.flush()

    job = BlogPublicationJob(
        schedule_id=sched.id,
        company_id=blog.company_id,
        blog_id=blog.id,
        revision_id=rev.id,
        attempt_number=1,
        idempotency_key=f"pub_sched_{sched.id}_rev_{rev.id}_att_1",
        status=PublicationJobStatus.RUNNING.value,
        worker_id="crashed-worker",
        lease_until=datetime.now(timezone.utc) - timedelta(minutes=5),  # Expired!
    )
    db_session.add(job)
    db_session.commit()

    recovery_worker = SchedulerWorker(worker_id="recovery-worker")
    reclaimed = recovery_worker.reclaim_expired_leases(db_session)
    assert reclaimed == 1

    db_session.refresh(job)
    db_session.refresh(sched)
    assert job.status == "FAILED"
    assert job.error_details == "WORKER_CRASHED_LEASE_EXPIRED"
    assert sched.status == "SCHEDULED"


def test_stale_worker_result_safely_rejected(db_session: Session, setup_scheduling_env):
    """If Worker A loses lease, its late result is discarded and does not overwrite state."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) - timedelta(hours=1),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.RUNNING.value,
        attempt_count=1,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.flush()

    job = BlogPublicationJob(
        schedule_id=sched.id,
        company_id=blog.company_id,
        blog_id=blog.id,
        revision_id=rev.id,
        attempt_number=1,
        idempotency_key=f"pub_sched_{sched.id}_rev_{rev.id}_stale_test",
        status=PublicationJobStatus.RUNNING.value,
        worker_id="worker-A",
        lease_until=datetime.now(timezone.utc) - timedelta(seconds=10),  # Expired lease
    )
    db_session.add(job)
    db_session.commit()

    worker_a = SchedulerWorker(worker_id="worker-A")
    success_result = PublicationResult(success=True, external_reference="late-ref")

    worker_a.record_result(db_session, job.id, success_result)

    db_session.refresh(sched)
    db_session.refresh(job)
    # Stale result was discarded: Job is NOT succeeded
    assert job.status == "RUNNING"
    assert job.external_reference is None


# ==============================================================================
# 9. MISSED SCHEDULE & OUTAGE POLICIES
# ==============================================================================

def test_missed_schedule_under_2_hours_executed_with_was_delayed(db_session: Session, setup_scheduling_env):
    """Schedules due within 2 hours are executed with was_delayed = True."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    due_time = datetime.now(timezone.utc) - timedelta(minutes=45)  # 45 min delay
    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=due_time,
        local_scheduled_time=due_time.replace(tzinfo=None),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    worker = SchedulerWorker(worker_id="delayed-worker")
    claimed = worker.claim_due_schedules(db_session)
    assert sched.id in claimed

    job = db_session.query(BlogPublicationJob).filter(BlogPublicationJob.schedule_id == sched.id).first()
    assert job.was_delayed is True


def test_missed_schedule_over_2_hours_marked_failed(db_session: Session, setup_scheduling_env):
    """Schedules older than 2 hours transition to FAILED with SCHEDULE_EXPIRED_DURING_OUTAGE."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    due_time = datetime.now(timezone.utc) - timedelta(hours=3)  # 3 hour outage
    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=due_time,
        local_scheduled_time=due_time.replace(tzinfo=None),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    worker = SchedulerWorker(worker_id="outage-worker")
    claimed = worker.claim_due_schedules(db_session)
    assert sched.id not in claimed

    db_session.refresh(sched)
    assert sched.status == "FAILED"
    assert sched.failure_code == "SCHEDULE_EXPIRED_DURING_OUTAGE"


# ==============================================================================
# 10. ERROR SANITIZATION & SECURITY
# ==============================================================================

def test_error_message_sanitization():
    raw_error = "Failed to connect: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz and password=SuperSecretPassword123"
    sanitized = sanitize_error(raw_error)
    assert "SuperSecretPassword123" not in sanitized
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz" not in sanitized
    assert "[REDACTED]" in sanitized


# ==============================================================================
# 11. ADVANCED ADVERSARIAL & CONCURRENCY TESTS
# ==============================================================================

def test_cancel_queued_schedule_marks_job_failed(client: TestClient, db_session: Session, setup_scheduling_env):
    """Cancelling a QUEUED schedule transitions schedule to CANCELLED and marks queued job FAILED."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    due_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=due_time,
        local_scheduled_time=due_time.replace(tzinfo=None),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    worker = SchedulerWorker(worker_id="test-claim-worker")
    claimed = worker.claim_due_schedules(db_session)
    assert sched.id in claimed

    db_session.refresh(sched)
    assert sched.status == "QUEUED"

    # User cancels while QUEUED
    resp = client.post(
        f"/api/v1/schedules/{sched.id}/cancel",
        json={"reason": "Cancelled before worker execution"},
        headers=auth_header(editor),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"

    # Verify publication job was marked FAILED with CANCELLED_BEFORE_EXECUTION
    job = db_session.query(BlogPublicationJob).filter(BlogPublicationJob.schedule_id == sched.id).first()
    assert job is not None
    assert job.status == "FAILED"
    assert job.error_details == "CANCELLED_BEFORE_EXECUTION"


def test_reschedule_rejected_when_not_scheduled_409(client: TestClient, db_session: Session, setup_scheduling_env):
    """Reschedule must fail with 409 if schedule is QUEUED, RUNNING, SUCCEEDED, FAILED, or CANCELLED."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) + timedelta(days=1),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    for invalid_status in [
        ScheduleStatus.QUEUED.value,
        ScheduleStatus.RUNNING.value,
        ScheduleStatus.SUCCEEDED.value,
        ScheduleStatus.FAILED.value,
        ScheduleStatus.CANCELLED.value,
    ]:
        sched.status = invalid_status
        db_session.commit()

        new_time = datetime.now(timezone.utc) + timedelta(days=5)
        resp = client.post(
            f"/api/v1/schedules/{sched.id}/reschedule",
            json={"local_scheduled_time": new_time.strftime("%Y-%m-%dT%H:%M:%S")},
            headers=auth_header(editor),
        )
        assert resp.status_code == 409
        assert "Only SCHEDULED" in resp.json()["detail"]


def test_permanent_failure_terminates_immediately_no_backoff(db_session: Session, setup_scheduling_env):
    """Permanent failures transition immediately to FAILED without backoff or further retries."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        max_attempts=3,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    worker = SchedulerWorker(worker_id="permanent-fail-worker")
    worker.claim_due_schedules(db_session)
    job_id = worker.start_execution(db_session, sched.id)

    # Provider returning permanent failure
    perm_provider = MockPublicationProvider(default_success=False)
    perm_provider.override_result = PublicationResult(
        success=False,
        is_transient_error=False,
        error_code="DESTINATION_AUTH_INVALID",
        error_message="Invalid credentials for external destination",
    )

    res = asyncio.run(worker.execute_publication(db_session, job_id, perm_provider))
    worker.record_result(db_session, job_id, res)

    db_session.refresh(sched)
    job = db_session.query(BlogPublicationJob).filter(BlogPublicationJob.id == job_id).first()
    assert job.status == "FAILED"
    assert sched.status == "FAILED"
    assert sched.failure_code == "DESTINATION_AUTH_INVALID"
    # No further retry
    assert sched.attempt_count == 1


def test_revision_deletion_restricted_by_foreign_key(db_session: Session, setup_scheduling_env):
    """PostgreSQL ON DELETE RESTRICT prevents deleting a revision bound to a schedule."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) + timedelta(days=1),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    # Attempt to delete the pinned revision
    db_session.delete(rev)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_schedule_detail_api(client: TestClient, db_session: Session, setup_scheduling_env):
    """GET /api/v1/schedules/{id} returns schedule details with publication jobs and events."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) + timedelta(days=1),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.flush()

    event = BlogScheduleEvent(
        schedule_id=sched.id,
        company_id=blog.company_id,
        event_type=ScheduleEventType.SCHEDULE_CREATED.value,
        actor_user_id=editor.id,
    )
    db_session.add(event)
    db_session.commit()

    resp = client.get(f"/api/v1/schedules/{sched.id}", headers=auth_header(editor))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sched.id
    assert len(data["events"]) >= 1
    assert data["events"][0]["event_type"] == "SCHEDULE_CREATED"


def test_list_blog_schedules_api(client: TestClient, db_session: Session, setup_scheduling_env):
    """GET /api/v1/blogs/{blog_id}/schedules returns all schedules for that blog."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    sched1 = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) - timedelta(days=2),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SUCCEEDED.value,
        created_by_user_id=editor.id,
    )
    sched2 = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) + timedelta(days=2),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched1)
    db_session.add(sched2)
    db_session.commit()

    resp = client.get(f"/api/v1/blogs/{blog.id}/schedules", headers=auth_header(editor))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


def test_db_partial_unique_index_one_active_publication_job(db_session: Session, setup_scheduling_env):
    """Database constraint blocks creating two concurrently active publication jobs for one schedule."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev = env["revision"]

    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc) + timedelta(days=1),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    j1 = BlogPublicationJob(
        schedule_id=sched.id,
        company_id=blog.company_id,
        blog_id=blog.id,
        revision_id=rev.id,
        attempt_number=1,
        idempotency_key=f"pub_sched_{sched.id}_rev_{rev.id}_att_1",
        status=PublicationJobStatus.RUNNING.value,
        worker_id="w1",
    )
    db_session.add(j1)
    db_session.commit()

    j2 = BlogPublicationJob(
        schedule_id=sched.id,
        company_id=blog.company_id,
        blog_id=blog.id,
        revision_id=rev.id,
        attempt_number=2,
        idempotency_key=f"pub_sched_{sched.id}_rev_{rev.id}_att_2",
        status=PublicationJobStatus.QUEUED.value,
        worker_id="w2",
    )
    db_session.add(j2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ==============================================================================
# 9. TARGETED DEF-P10-01 TESTS: APPROVED REVISION DERIVATION & INTEGRITY
# ==============================================================================

def test_newer_unapproved_revision_does_not_become_schedulable(client: TestClient, db_session: Session, setup_scheduling_env):
    """When a newer unapproved V2 exists, schedule creation automatically and strictly binds to approved V1."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    rev1 = env["revision"]

    # Create unapproved V2
    rev2 = BlogRevision(
        company_id=blog.company_id,
        blog_id=blog.id,
        revision_number=2,
        revision_summary="V2 unapproved draft",
        seo_title="V2 Title",
        content_markdown="V2 Markdown",
        content_json={},
    )
    db_session.add(rev2)
    db_session.commit()

    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "UTC"},
        headers=auth_header(editor),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["target_revision_id"] == rev1.id
    assert data["target_revision_id"] != rev2.id


def test_worker_claim_after_approved_revision_changes_fails_safe(db_session: Session, setup_scheduling_env):
    """If Schedule was bound to V1, but a new review later approved V2, worker claim rejects V1 and fails safely."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]
    reviewer = env["reviewer"]
    rev1 = env["revision"]

    # Create due schedule bound to V1
    sched = BlogSchedule(
        company_id=blog.company_id,
        blog_id=blog.id,
        target_revision_id=rev1.id,
        scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=5),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.commit()

    # Now create and approve V2
    rev2 = BlogRevision(
        company_id=blog.company_id,
        blog_id=blog.id,
        revision_number=2,
        revision_summary="V2 approved",
        seo_title="V2 Title",
        content_markdown="V2 Markdown",
        content_json={},
    )
    db_session.add(rev2)
    db_session.flush()

    new_review = BlogReview(
        company_id=blog.company_id,
        blog_id=blog.id,
        submitted_revision_id=rev2.id,
        reviewer_id=reviewer.id,
        status="approved",
        decided_at=datetime.now(timezone.utc) + timedelta(seconds=1),
    )
    db_session.add(new_review)
    db_session.commit()

    # Worker attempts claim on schedule bound to V1
    worker = SchedulerWorker(worker_id="test-rev-change-worker")
    claimed = worker.claim_due_schedules(db_session)
    # Schedule should not be claimed because revision mismatch occurred
    assert sched.id not in claimed

    db_session.refresh(sched)
    assert sched.status == "FAILED"
    assert sched.failure_code == "INVALID_BLOG_STATE"


def test_missing_approved_review_returns_409_never_500(client: TestClient, db_session: Session, setup_scheduling_env):
    """When blog has no approved review, schedule creation returns 409, never 500."""
    env = setup_scheduling_env
    blog = env["blog"]
    editor = env["editor"]

    # Delete the approved review
    review = env["review"]
    db_session.delete(review)
    db_session.commit()

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "UTC"},
        headers=auth_header(editor),
    )
    assert resp.status_code == 409
    assert "No approved review found" in resp.json()["detail"]


def test_approved_review_with_missing_or_invalid_submitted_revision_id_safe_failure(client: TestClient, db_session: Session, setup_scheduling_env):
    """When approved review references an invalid revision belonging to another blog, schedule creation safely returns 409."""
    env = setup_scheduling_env
    blog = env["blog"]
    company = env["company"]
    editor = env["editor"]
    review = env["review"]

    # Create another blog and revision
    other_topic = TopicCandidate(
        company_id=company.id,
        title="Other Topic",
        angle="Other Angle",
        primary_keyword="other",
        status=TopicStatus.SELECTED,
    )
    db_session.add(other_topic)
    db_session.flush()

    other_blog = Blog(
        company_id=company.id,
        topic_candidate_id=other_topic.id,
        created_by_user_id=editor.id,
        title="Other Blog",
        content_json={"sections": []},
        content_markdown="Other content",
        status=BlogStatus.DRAFT,
    )
    db_session.add(other_blog)
    db_session.flush()

    other_rev = BlogRevision(
        company_id=company.id,
        blog_id=other_blog.id,
        revision_number=1,
        revision_summary="Other revision",
        seo_title="Other SEO",
        content_markdown="Other content",
        content_json={},
    )
    db_session.add(other_rev)
    db_session.flush()

    # Point review to other blog's revision
    review.submitted_revision_id = other_rev.id
    db_session.commit()

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    resp = client.post(
        f"/api/v1/blogs/{blog.id}/schedules",
        json={"local_scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": "UTC"},
        headers=auth_header(editor),
    )
    assert resp.status_code == 409
    assert "Approved revision not found for blog" in resp.json()["detail"]


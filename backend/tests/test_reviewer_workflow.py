"""
Phase 9 — Reviewer Workflow & Editorial Governance Test Suite

Comprehensive tests verifying:
1. Editorial review lifecycle: submit (with atomic Phase 7 validation gating), withdraw.
2. Review decisions: approve, reject, request_changes (with feedback injection into Phase 8 chat).
3. Post-review iterative workflow across multiple review cycles (V0 -> V1 -> V2).
4. Separation of Duties (SoD): authors cannot review own blogs (with solo-tenant break-glass exception).
5. Reviewer mutation blocking on Phase 8 (POST /chat and POST /restore blocked when not draft/changes_requested).
6. Shared reviewer queue (FIFO order, tenant isolation, exclusion of decided reviews).
7. Tenant isolation and strict RBAC enforcement.
"""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.blog import Blog, BlogStatus
from backend.app.models.blog_chat import (
    BlogChatMessage,
    BlogChatThread,
    BlogRevision,
    ChatMessageType,
    ChatSenderType,
)
from backend.app.models.blog_format import BlogFormat
from backend.app.models.blog_review import BlogReview, ReviewStatus
from backend.app.models.company import Company
from backend.app.models.topic_candidate import TopicCandidate, TopicStatus
from backend.app.models.user import User, UserRole, UserStatus
from backend.app.schemas.blog import BlogDraftSection, StructuredBlogDraft
from backend.app.core.security import hash_password
from backend.app.services.auth_service import create_user_access_token
from backend.app.services.blog_generation_provider import render_blog_to_markdown
from backend.app.services.blog_revision_service import BlogRevisionService


# ── Test Setup Helpers ────────────────────────────────────────────────

def create_valid_test_draft(
    primary_keyword: str = "cloud observability",
) -> StructuredBlogDraft:
    """Construct a fully Phase 7-compliant StructuredBlogDraft."""
    seo_title = f"{primary_keyword.title()}: Complete Architecture Guide for 2026"
    if len(seo_title) < 55:
        seo_title = seo_title.ljust(58, "!")
    elif len(seo_title) > 60:
        seo_title = seo_title[:58]

    meta_desc = (
        f"Discover the complete guide to {primary_keyword} for modern distributed systems. "
        "Learn key architectural patterns, telemetry tools, and metrics today."
    )
    if len(meta_desc) < 140:
        meta_desc = meta_desc.ljust(145, ".")
    elif len(meta_desc) > 160:
        meta_desc = meta_desc[:150]

    return StructuredBlogDraft(
        h1_title=f"The Definitive Guide to {primary_keyword.title()}",
        seo_title=seo_title,
        meta_description=meta_desc,
        primary_keyword=primary_keyword,
        introduction=(
            f"Understanding {primary_keyword} is essential for scaling mission-critical platforms. "
            "In this comprehensive technical blueprint, we analyze core architectural paradigms, "
            "telemetry instrumentation strategies, and end-to-end data pipelines for high-reliability systems."
        ),
        sections=[
            BlogDraftSection(
                heading=f"Core Architectural Foundations of {primary_keyword.title()}",
                level=2,
                content=(
                    "Distributed systems require real-time trace propagation and low-overhead collectors. "
                    "By standardizing semantic conventions across microservices, teams achieve holistic visibility."
                ),
            ),
            BlogDraftSection(
                heading="High-Performance Telemetry Pipelines and Storage",
                level=2,
                content=(
                    "Ingestion pipelines must decouple synchronous web workers from write-heavy databases. "
                    "Buffering metrics with Kafka and ClickHouse ensures predictable latency during traffic spikes."
                ),
            ),
            BlogDraftSection(
                heading="Automated Anomaly Detection and Mitigation Strategies",
                level=2,
                content=(
                    "Proactive alerting relies on adaptive statistical thresholds rather than static rules. "
                    "Automated circuit breakers prevent cascading failures across interconnected service meshes."
                ),
            ),
        ],
        conclusion=(
            f"In summary, implementing resilient {primary_keyword} is a foundational prerequisite for enterprise scalability. "
            "By investing in robust telemetry infrastructure and automated governance, engineering organizations "
            "ensure high availability and sustained operational velocity."
        ),
        call_to_action=(
            f"Discover how our platform accelerates enterprise {primary_keyword} workflows. "
            "Schedule an architecture review with our specialist team today."
        ),
    )


def auth_header(user: User) -> Dict[str, str]:
    token = create_user_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def setup_blog_workflow(
    db_session: Session,
    create_company,
    create_user,
):
    """Fixture creating company, admin, author/editor, separate reviewer, and a valid draft blog."""
    def _create(company_name: str = "Review Corp"):
        company = create_company(name=company_name)
        admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
        editor = create_user(company_id=company.id, role=UserRole.EDITOR)
        reviewer = create_user(company_id=company.id, role=UserRole.REVIEWER)

        # Company blog format
        blog_format = BlogFormat(
            company_id=company.id,
            format_definition="Standard company blog format with introduction and conclusion.",
            version=1,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(blog_format)

        topic = TopicCandidate(
            company_id=company.id,
            title="Mastering Cloud Observability in Modern Systems",
            angle="Technical architecture blueprint",
            primary_keyword="cloud observability",
            status=TopicStatus.SELECTED,
        )
        db_session.add(topic)
        db_session.commit()
        db_session.refresh(topic)

        draft = create_valid_test_draft("cloud observability")
        blog = Blog(
            company_id=company.id,
            topic_candidate_id=topic.id,
            created_by_user_id=editor.id,
            title=draft.h1_title,
            slug="mastering-cloud-observability-in-modern-systems",
            primary_keyword=draft.primary_keyword,
            seo_title=draft.seo_title,
            meta_description=draft.meta_description,
            content_json=draft.model_dump(),
            content_markdown=render_blog_to_markdown(draft),
            status=BlogStatus.DRAFT,
            format_version=1,
            generation_metadata={"generation_mode": "test"},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(blog)
        db_session.commit()
        db_session.refresh(blog)

        # Ensure initial revision V0
        rev_service = BlogRevisionService(db=db_session)
        v0 = rev_service.ensure_initial_revision_v0(blog=blog, editor_id=editor.id)

        return {
            "company": company,
            "admin": admin,
            "editor": editor,
            "reviewer": reviewer,
            "topic": topic,
            "blog": blog,
            "v0": v0,
        }

    return _create


# ── Group 1: Submission & Gating Tests ─────────────────────────────────

def test_submit_for_review_success(client: TestClient, setup_blog_workflow):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    response = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        json={"submission_note": "Ready for technical review"},
        headers=auth_header(editor),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["blog_id"] == blog.id
    assert data["submitted_revision_id"] == ctx["v0"].id
    assert data["submission_note"] == "Ready for technical review"
    assert data["reviewer_id"] is None


def test_submit_for_review_auto_creates_v0_if_missing(
    client: TestClient, setup_blog_workflow, db_session: Session
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    # Delete V0 revision manually to test auto-creation
    db_session.query(BlogRevision).filter(BlogRevision.blog_id == blog.id).delete()
    db_session.commit()

    response = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        json={"submission_note": "Initial submission"},
        headers=auth_header(editor),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    # Auto-created revision should be present
    rev = db_session.query(BlogRevision).filter(BlogRevision.blog_id == blog.id).first()
    assert rev is not None
    assert rev.revision_number == 0
    assert data["submitted_revision_id"] == rev.id


def test_submit_for_review_twice_rejected_409(client: TestClient, setup_blog_workflow):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    # First submit
    res1 = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        headers=auth_header(editor),
    )
    assert res1.status_code == 201

    # Second submit while pending
    res2 = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        headers=auth_header(editor),
    )
    assert res2.status_code == 409
    assert "already has an active pending review" in res2.json()["detail"] or "cannot be submitted" in res2.json()["detail"]


def test_submit_for_review_non_draft_rejected_409(
    client: TestClient, setup_blog_workflow, db_session: Session
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    blog.status = BlogStatus.GENERATING
    db_session.commit()

    response = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        headers=auth_header(editor),
    )
    assert response.status_code == 409
    assert "generating" in response.json()["detail"]


def test_submit_for_review_phase7_failure_blocked_422(
    client: TestClient, setup_blog_workflow, db_session: Session
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    # Invalidate blog content (empty intro and bad slug)
    draft_dict = dict(blog.content_json)
    draft_dict["introduction"] = "Too short"
    blog.content_json = draft_dict
    blog.slug = "INVALID SLUG WITH SPACES"
    db_session.commit()

    response = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        headers=auth_header(editor),
    )
    assert response.status_code == 422
    assert "failed Phase 7 deterministic validation" in response.json()["detail"]["message"]

    # Verify blog status stayed DRAFT and 0 reviews were created
    db_session.refresh(blog)
    assert blog.status == BlogStatus.DRAFT
    review_count = db_session.query(BlogReview).filter(BlogReview.blog_id == blog.id).count()
    assert review_count == 0


def test_withdraw_review_success(client: TestClient, setup_blog_workflow, db_session: Session):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    # Submit
    client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))
    db_session.refresh(blog)
    assert blog.status == BlogStatus.PENDING_REVIEW

    # Withdraw
    withdraw_res = client.post(
        f"/api/v1/blogs/{blog.id}/withdraw-review",
        headers=auth_header(editor),
    )
    assert withdraw_res.status_code == 200
    data = withdraw_res.json()
    assert data["status"] == "withdrawn"
    assert data["decided_at"] is not None

    db_session.refresh(blog)
    assert blog.status == BlogStatus.DRAFT


def test_withdraw_review_on_non_pending_rejected_409(client: TestClient, setup_blog_workflow):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    # Withdraw when still in draft
    response = client.post(
        f"/api/v1/blogs/{blog.id}/withdraw-review",
        headers=auth_header(editor),
    )
    assert response.status_code == 409
    assert "draft" in response.json()["detail"]


# ── Group 2: Review Decisions ──────────────────────────────────────────

def test_decide_approve_success(client: TestClient, setup_blog_workflow, db_session: Session):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    # Submit
    sub_res = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))
    review_id = sub_res.json()["id"]

    # Reviewer approves
    decide_res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "approve", "reviewer_comment": "Excellent architecture breakdown."},
        headers=auth_header(reviewer),
    )
    assert decide_res.status_code == 200
    data = decide_res.json()
    assert data["status"] == "approved"
    assert data["reviewer_id"] == reviewer.id
    assert data["decided_at"] is not None
    assert data["reviewer_comment"] == "Excellent architecture breakdown."

    db_session.refresh(blog)
    assert blog.status == BlogStatus.APPROVED


def test_decide_reject_success(client: TestClient, setup_blog_workflow, db_session: Session):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    sub_res = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))
    review_id = sub_res.json()["id"]

    decide_res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "reject", "reviewer_comment": "Topic misaligned with company direction."},
        headers=auth_header(reviewer),
    )
    assert decide_res.status_code == 200
    data = decide_res.json()
    assert data["status"] == "rejected"
    assert data["reviewer_id"] == reviewer.id

    db_session.refresh(blog)
    assert blog.status == BlogStatus.REJECTED


def test_decide_request_changes_success(client: TestClient, setup_blog_workflow, db_session: Session):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    sub_res = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))
    review_id = sub_res.json()["id"]

    feedback_text = "Please expand the Kafka telemetry section with concrete queue configuration advice."
    decide_res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "request_changes", "feedback": feedback_text},
        headers=auth_header(reviewer),
    )
    assert decide_res.status_code == 200
    data = decide_res.json()
    assert data["status"] == "changes_requested"
    assert data["feedback"] == feedback_text

    db_session.refresh(blog)
    assert blog.status == BlogStatus.CHANGES_REQUESTED

    # Verify editorial feedback message injected into Phase 8 chat thread
    thread = db_session.query(BlogChatThread).filter(BlogChatThread.blog_id == blog.id).first()
    assert thread is not None
    messages = (
        db_session.query(BlogChatMessage)
        .filter(BlogChatMessage.thread_id == thread.id)
        .order_by(BlogChatMessage.created_at.desc())
        .all()
    )
    assert len(messages) >= 1
    feedback_msg = messages[0]
    assert feedback_msg.message_type == "review_feedback"
    assert feedback_msg.sender_type == ChatSenderType.SYSTEM.value
    assert feedback_text in feedback_msg.content
    assert feedback_msg.message_metadata["review_id"] == review_id


def test_decide_request_changes_missing_feedback_rejected_422(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    sub_res = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))
    review_id = sub_res.json()["id"]

    # Empty feedback on request_changes
    decide_res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "request_changes", "feedback": "   "},
        headers=auth_header(reviewer),
    )
    assert decide_res.status_code == 422


def test_decide_on_already_decided_review_rejected_409(client: TestClient, setup_blog_workflow):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    sub_res = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))
    review_id = sub_res.json()["id"]

    # First decision
    client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "approve"},
        headers=auth_header(reviewer),
    )

    # Second decision attempt
    res2 = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "reject", "reviewer_comment": "Rejection note."},
        headers=auth_header(reviewer),
    )
    assert res2.status_code == 409
    assert "no longer pending" in res2.json()["detail"]


def test_decide_on_withdrawn_review_rejected_409(client: TestClient, setup_blog_workflow):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    sub_res = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))
    review_id = sub_res.json()["id"]

    # Withdraw
    client.post(f"/api/v1/blogs/{blog.id}/withdraw-review", headers=auth_header(editor))

    # Attempt decision on withdrawn
    res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "approve"},
        headers=auth_header(reviewer),
    )
    assert res.status_code == 409


def test_decide_on_superseded_revision_rejected_409(
    client: TestClient, setup_blog_workflow, db_session: Session
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    sub_res = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))
    review_id = sub_res.json()["id"]

    # Create a newer revision behind the scenes
    rev2 = BlogRevision(
        company_id=blog.company_id,
        blog_id=blog.id,
        revision_number=99,
        revision_summary="Sneaky concurrent edit",
        content_json=blog.content_json,
        content_markdown=blog.content_markdown,
        created_at=datetime.utcnow(),
    )
    db_session.add(rev2)
    db_session.commit()

    decide_res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "approve"},
        headers=auth_header(reviewer),
    )
    assert decide_res.status_code == 409
    assert "superseded revision" in decide_res.json()["detail"]


# ── Group 3: Multi-Cycle Post-Review Workflow ──────────────────────────

def test_full_iterative_editorial_cycle(client: TestClient, setup_blog_workflow, db_session: Session):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    # Cycle 1: Submit V0
    sub1 = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))
    assert sub1.status_code == 201
    rev1_id = sub1.json()["id"]

    # Cycle 1: Reviewer requests changes
    client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{rev1_id}/decide",
        json={"decision": "request_changes", "feedback": "Add Kafka queue configuration advice."},
        headers=auth_header(reviewer),
    )

    db_session.refresh(blog)
    assert blog.status == BlogStatus.CHANGES_REQUESTED

    # Editor performs revision via Phase 8 chat
    chat_res = client.post(
        f"/api/v1/blogs/{blog.id}/chat",
        json={
            "message": "Add Kafka queue configuration advice to the telemetry section",
            "base_revision_id": ctx["v0"].id,
        },
        headers=auth_header(editor),
    )
    assert chat_res.status_code == 200
    v1_id = chat_res.json()["revision"]["id"]

    # Cycle 2: Editor re-submits blog for review
    sub2 = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        json={"submission_note": "Addressed Kafka advice."},
        headers=auth_header(editor),
    )
    assert sub2.status_code == 201
    rev2_id = sub2.json()["id"]
    assert sub2.json()["submitted_revision_id"] == v1_id

    # Cycle 2: Reviewer approves
    app_res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{rev2_id}/decide",
        json={"decision": "approve", "reviewer_comment": "Looks great now!"},
        headers=auth_header(reviewer),
    )
    assert app_res.status_code == 200

    db_session.refresh(blog)
    assert blog.status == BlogStatus.APPROVED


def test_review_history_endpoint_returns_chronological_cycles(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    # Cycle 1: Submit & Request changes
    s1 = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{s1['id']}/decide",
        json={"decision": "request_changes", "feedback": "Fix intro"},
        headers=auth_header(reviewer),
    )

    # Cycle 2: Submit & Approve
    s2 = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{s2['id']}/decide",
        json={"decision": "approve"},
        headers=auth_header(reviewer),
    )

    history_res = client.get(f"/api/v1/blogs/{blog.id}/reviews", headers=auth_header(editor))
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 2
    assert history[0]["id"] == s1["id"]
    assert history[0]["status"] == "changes_requested"
    assert history[1]["id"] == s2["id"]
    assert history[1]["status"] == "approved"


def test_review_detail_endpoint_success(client: TestClient, setup_blog_workflow):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    s1 = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        json={"submission_note": "Check detail endpoint"},
        headers=auth_header(editor),
    ).json()

    res = client.get(f"/api/v1/blogs/{blog.id}/reviews/{s1['id']}", headers=auth_header(editor))
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == s1["id"]
    assert detail["blog_id"] == blog.id
    assert detail["submitted_revision_number"] == 0
    assert detail["blog_title"] == blog.title
    assert detail["submitted_by_user_id"] == editor.id


# ── Group 4: Phase 8 Mutation Blocking ─────────────────────────────────

def test_phase8_chat_mutation_blocked_when_pending_review_409(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    # Submit for review -> blog is pending_review
    client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))

    # Editor attempts chat mutation
    res = client.post(
        f"/api/v1/blogs/{blog.id}/chat",
        json={"message": "Try to edit while pending review", "base_revision_id": ctx["v0"].id},
        headers=auth_header(editor),
    )
    assert res.status_code == 409
    assert "pending_review" in res.json()["detail"]


def test_phase8_chat_mutation_blocked_when_approved_409(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{s['id']}/decide",
        json={"decision": "approve"},
        headers=auth_header(reviewer),
    )

    res = client.post(
        f"/api/v1/blogs/{blog.id}/chat",
        json={"message": "Try to edit while approved", "base_revision_id": ctx["v0"].id},
        headers=auth_header(editor),
    )
    assert res.status_code == 409
    assert "approved" in res.json()["detail"]


def test_phase8_chat_mutation_blocked_when_rejected_409(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{s['id']}/decide",
        json={"decision": "reject", "reviewer_comment": "Rejected."},
        headers=auth_header(reviewer),
    )

    res = client.post(
        f"/api/v1/blogs/{blog.id}/chat",
        json={"message": "Try to edit while rejected", "base_revision_id": ctx["v0"].id},
        headers=auth_header(editor),
    )
    assert res.status_code == 409
    assert "rejected" in res.json()["detail"]


def test_phase8_restore_revision_blocked_when_pending_review_409(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor))

    res = client.post(
        f"/api/v1/blogs/{blog.id}/revisions/{ctx['v0'].id}/restore",
        headers=auth_header(editor),
    )
    assert res.status_code == 409
    assert "pending_review" in res.json()["detail"]


def test_phase8_restore_revision_blocked_when_approved_409(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{s['id']}/decide",
        json={"decision": "approve"},
        headers=auth_header(reviewer),
    )

    res = client.post(
        f"/api/v1/blogs/{blog.id}/revisions/{ctx['v0'].id}/restore",
        headers=auth_header(editor),
    )
    assert res.status_code == 409
    assert "approved" in res.json()["detail"]


def test_phase8_restore_revision_blocked_when_rejected_409(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{s['id']}/decide",
        json={"decision": "reject", "reviewer_comment": "Rejected."},
        headers=auth_header(reviewer),
    )

    res = client.post(
        f"/api/v1/blogs/{blog.id}/revisions/{ctx['v0'].id}/restore",
        headers=auth_header(editor),
    )
    assert res.status_code == 409
    assert "rejected" in res.json()["detail"]


def test_phase8_chat_mutation_allowed_when_changes_requested(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{s['id']}/decide",
        json={"decision": "request_changes", "feedback": "Expand sections"},
        headers=auth_header(reviewer),
    )

    # Allowed in changes_requested!
    res = client.post(
        f"/api/v1/blogs/{blog.id}/chat",
        json={"message": "Expand sections as requested", "base_revision_id": ctx["v0"].id},
        headers=auth_header(editor),
    )
    assert res.status_code == 200


# ── Group 5: Separation of Duties (SoD) ────────────────────────────────

def test_sod_author_cannot_approve_own_blog_403(
    client: TestClient, setup_blog_workflow, db_session: Session
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    admin = ctx["admin"]

    # Set blog author to admin
    blog.created_by_user_id = admin.id
    db_session.commit()

    # Admin submits blog
    sub_res = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(admin))
    review_id = sub_res.json()["id"]

    # Admin attempts to approve their own blog
    decide_res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "approve"},
        headers=auth_header(admin),
    )
    assert decide_res.status_code == 403
    assert "Separation of Duties violation" in decide_res.json()["detail"]


def test_sod_author_cannot_reject_own_blog_403(
    client: TestClient, setup_blog_workflow, db_session: Session
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    admin = ctx["admin"]

    blog.created_by_user_id = admin.id
    db_session.commit()

    sub_res = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(admin))
    review_id = sub_res.json()["id"]

    decide_res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "reject", "reviewer_comment": "Self-review rejection attempt."},
        headers=auth_header(admin),
    )
    assert decide_res.status_code == 403
    assert "Separation of Duties violation" in decide_res.json()["detail"]


def test_sod_author_cannot_request_changes_on_own_blog_403(
    client: TestClient, setup_blog_workflow, db_session: Session
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    admin = ctx["admin"]

    blog.created_by_user_id = admin.id
    db_session.commit()

    sub_res = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(admin))
    review_id = sub_res.json()["id"]

    decide_res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "request_changes", "feedback": "Self-review rejected"},
        headers=auth_header(admin),
    )
    assert decide_res.status_code == 403
    assert "Separation of Duties violation" in decide_res.json()["detail"]


def test_sod_solo_tenant_break_glass_admin_can_approve(
    client: TestClient, create_company, create_user, db_session: Session
):
    company = create_company(name="Solo Startup")
    solo_admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)

    # Blog format
    blog_format = BlogFormat(
        company_id=company.id,
        format_definition="Standard company blog format with introduction and conclusion.",
        version=1,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(blog_format)

    topic = TopicCandidate(
        company_id=company.id,
        title="Solo Cloud Insights",
        angle="Solo architecture",
        primary_keyword="cloud observability",
        status=TopicStatus.SELECTED,
    )
    db_session.add(topic)
    db_session.commit()

    draft = create_valid_test_draft("cloud observability")
    blog = Blog(
        company_id=company.id,
        topic_candidate_id=topic.id,
        created_by_user_id=solo_admin.id,
        title=draft.h1_title,
        slug="solo-cloud-insights",
        primary_keyword=draft.primary_keyword,
        seo_title=draft.seo_title,
        meta_description=draft.meta_description,
        content_json=draft.model_dump(),
        content_markdown=render_blog_to_markdown(draft),
        status=BlogStatus.DRAFT,
        format_version=1,
        generation_metadata={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(blog)
    db_session.commit()

    rev_service = BlogRevisionService(db=db_session)
    rev_service.ensure_initial_revision_v0(blog=blog, editor_id=solo_admin.id)

    # Submit
    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(solo_admin)).json()

    # Solo break-glass: solo admin can approve
    app_res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{s['id']}/decide",
        json={"decision": "approve"},
        headers=auth_header(solo_admin),
    )
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"


# ── Group 6: Shared Reviewer Queue ─────────────────────────────────────

def test_pending_reviews_queue_fifo_ordering(
    client: TestClient, setup_blog_workflow, create_user, db_session: Session
):
    ctx = setup_blog_workflow()
    blog1 = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    # Submit blog 1
    client.post(
        f"/api/v1/blogs/{blog1.id}/submit-for-review",
        json={"submission_note": "Blog 1 first in line"},
        headers=auth_header(editor),
    )

    # Create blog 2 and submit
    topic2 = TopicCandidate(
        company_id=ctx["company"].id,
        title="Second Blog on Cloud Observability",
        angle="Second blueprint",
        primary_keyword="cloud observability",
        status=TopicStatus.SELECTED,
    )
    db_session.add(topic2)
    db_session.commit()

    draft2 = create_valid_test_draft("cloud observability")
    blog2 = Blog(
        company_id=ctx["company"].id,
        topic_candidate_id=topic2.id,
        created_by_user_id=editor.id,
        title=draft2.h1_title + " Part 2",
        slug="second-blog-cloud-observability",
        primary_keyword=draft2.primary_keyword,
        seo_title=draft2.seo_title,
        meta_description=draft2.meta_description,
        content_json=draft2.model_dump(),
        content_markdown=render_blog_to_markdown(draft2),
        status=BlogStatus.DRAFT,
        format_version=1,
        generation_metadata={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(blog2)
    db_session.commit()

    rev_service = BlogRevisionService(db=db_session)
    rev_service.ensure_initial_revision_v0(blog=blog2, editor_id=editor.id)

    client.post(
        f"/api/v1/blogs/{blog2.id}/submit-for-review",
        json={"submission_note": "Blog 2 second in line"},
        headers=auth_header(editor),
    )

    queue_res = client.get("/api/v1/blogs/reviews/pending", headers=auth_header(reviewer))
    assert queue_res.status_code == 200
    queue = queue_res.json()
    assert len(queue) >= 2
    # Verify FIFO: blog1 submitted before blog2
    assert queue[0]["blog_id"] == blog1.id
    assert queue[1]["blog_id"] == blog2.id


def test_pending_reviews_queue_excludes_decided_and_withdrawn(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    # Submit
    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()

    # Reviewer approves
    client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{s['id']}/decide",
        json={"decision": "approve"},
        headers=auth_header(reviewer),
    )

    # Queue should be empty of this blog
    queue_res = client.get("/api/v1/blogs/reviews/pending", headers=auth_header(reviewer))
    assert queue_res.status_code == 200
    blog_ids = [item["blog_id"] for item in queue_res.json()]
    assert blog.id not in blog_ids


# ── Group 7: Tenant Isolation & RBAC ───────────────────────────────────

def test_tenant_isolation_cross_company_review_access_404(
    client: TestClient, setup_blog_workflow, create_company, create_user
):
    ctx_a = setup_blog_workflow("Company A")
    blog_a = ctx_a["blog"]
    editor_a = ctx_a["editor"]

    # Company B
    comp_b = create_company(name="Company B")
    reviewer_b = create_user(company_id=comp_b.id, role=UserRole.REVIEWER)

    # Submit Company A blog
    s = client.post(f"/api/v1/blogs/{blog_a.id}/submit-for-review", headers=auth_header(editor_a)).json()
    review_id = s["id"]

    # Reviewer B tries to view or decide Company A review
    decide_res = client.post(
        f"/api/v1/blogs/{blog_a.id}/reviews/{review_id}/decide",
        json={"decision": "approve"},
        headers=auth_header(reviewer_b),
    )
    assert decide_res.status_code == 404

    history_res = client.get(
        f"/api/v1/blogs/{blog_a.id}/reviews",
        headers=auth_header(reviewer_b),
    )
    assert history_res.status_code == 404


def test_tenant_isolation_pending_queue_isolated(
    client: TestClient, setup_blog_workflow, create_company, create_user
):
    ctx_a = setup_blog_workflow("Company A")
    blog_a = ctx_a["blog"]
    editor_a = ctx_a["editor"]

    comp_b = create_company(name="Company B")
    reviewer_b = create_user(company_id=comp_b.id, role=UserRole.REVIEWER)

    # Submit blog for Company A
    client.post(f"/api/v1/blogs/{blog_a.id}/submit-for-review", headers=auth_header(editor_a))

    # Reviewer B queue must NOT show Company A's pending review
    queue_res = client.get("/api/v1/blogs/reviews/pending", headers=auth_header(reviewer_b))
    assert queue_res.status_code == 200
    blog_ids = [item["blog_id"] for item in queue_res.json()]
    assert blog_a.id not in blog_ids


def test_rbac_editor_cannot_decide_review_403(client: TestClient, setup_blog_workflow):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()

    # Editor tries to decide
    res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{s['id']}/decide",
        json={"decision": "approve"},
        headers=auth_header(editor),
    )
    assert res.status_code == 403


def test_rbac_reviewer_cannot_submit_review_403(client: TestClient, setup_blog_workflow):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    reviewer = ctx["reviewer"]

    # Reviewer tries to submit blog for review
    res = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        headers=auth_header(reviewer),
    )
    assert res.status_code == 403


def test_rbac_editor_cannot_view_pending_queue_403(client: TestClient, setup_blog_workflow):
    ctx = setup_blog_workflow()
    editor = ctx["editor"]

    res = client.get("/api/v1/blogs/reviews/pending", headers=auth_header(editor))
    assert res.status_code == 403


# ── Group 8: DEF-P9-02 — Reject Comment Validation ────────────────────

def test_def_p9_02_reject_with_missing_feedback_returns_422(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    review_id = s["id"]

    # Reject with completely missing feedback / reviewer_comment
    res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "reject"},
        headers=auth_header(reviewer),
    )
    assert res.status_code == 422
    assert "Reviewer feedback or comment is mandatory when rejecting a blog draft" in res.text


def test_def_p9_02_reject_with_null_feedback_returns_422(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    review_id = s["id"]

    # Reject with explicit null values
    res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "reject", "feedback": None, "reviewer_comment": None},
        headers=auth_header(reviewer),
    )
    assert res.status_code == 422
    assert "Reviewer feedback or comment is mandatory when rejecting a blog draft" in res.text


def test_def_p9_02_reject_with_empty_string_returns_422(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    review_id = s["id"]

    # Reject with empty string feedback
    res1 = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "reject", "feedback": ""},
        headers=auth_header(reviewer),
    )
    assert res1.status_code == 422

    # Reject with empty string reviewer_comment
    res2 = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "reject", "reviewer_comment": ""},
        headers=auth_header(reviewer),
    )
    assert res2.status_code == 422


def test_def_p9_02_reject_with_whitespace_returns_422(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    review_id = s["id"]

    # Reject with whitespace feedback
    res1 = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "reject", "feedback": "   \n\t  "},
        headers=auth_header(reviewer),
    )
    assert res1.status_code == 422

    # Reject with whitespace reviewer_comment
    res2 = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "reject", "reviewer_comment": "   "},
        headers=auth_header(reviewer),
    )
    assert res2.status_code == 422


def test_def_p9_02_reject_with_valid_feedback_or_comment_returns_200(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    # Submit
    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    review_id = s["id"]

    # Reject with non-empty reviewer_comment
    res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "reject", "reviewer_comment": "Content failed editorial alignment."},
        headers=auth_header(reviewer),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "rejected"
    assert data["reviewer_comment"] == "Content failed editorial alignment."


def test_def_p9_02_request_changes_existing_behavior_remains_correct(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    review_id = s["id"]

    # Missing feedback on request_changes -> 422
    res_err = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "request_changes"},
        headers=auth_header(reviewer),
    )
    assert res_err.status_code == 422

    # Valid feedback on request_changes -> 200
    res_ok = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "request_changes", "feedback": "Please expand on telemetry patterns."},
        headers=auth_header(reviewer),
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "changes_requested"


def test_def_p9_02_approve_with_no_comment_remains_valid(
    client: TestClient, setup_blog_workflow
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]
    reviewer = ctx["reviewer"]

    s = client.post(f"/api/v1/blogs/{blog.id}/submit-for-review", headers=auth_header(editor)).json()
    review_id = s["id"]

    # Approve with no comment/feedback remains valid
    res = client.post(
        f"/api/v1/blogs/{blog.id}/reviews/{review_id}/decide",
        json={"decision": "approve"},
        headers=auth_header(reviewer),
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved"


# ── Group 9: DEF-P9-01 — Concurrency & Revision Integrity ──────────────

def test_def_p9_01_chat_first_outcome_review_binds_newest_revision(
    client: TestClient, setup_blog_workflow, db_session: Session
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    # 1. Chat mutation occurs first and generates revision V1
    chat_res = client.post(
        f"/api/v1/blogs/{blog.id}/chat",
        json={"message": "Please refine the introduction section", "base_revision_id": ctx["v0"].id},
        headers=auth_header(editor),
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data.get("revision") is not None
    v1_id = chat_data["revision"]["id"]

    # 2. Submit for review runs subsequent to chat mutation
    sub_res = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        headers=auth_header(editor),
    )
    assert sub_res.status_code == 201
    sub_data = sub_res.json()

    # 3. Verify Outcome A invariant: review binds V1 (newest revision)
    assert sub_data["submitted_revision_id"] == v1_id
    assert sub_data["submitted_revision_id"] != ctx["v0"].id

    # 4. Verify blog state in DB
    db_session.expire_all()
    latest_rev = (
        db_session.query(BlogRevision)
        .filter(BlogRevision.blog_id == blog.id)
        .order_by(BlogRevision.revision_number.desc())
        .first()
    )
    assert latest_rev.id == v1_id
    assert latest_rev.revision_number == 1
    assert sub_data["submitted_revision_id"] == latest_rev.id


def test_def_p9_01_submit_first_outcome_chat_receives_409(
    client: TestClient, setup_blog_workflow, db_session: Session
):
    ctx = setup_blog_workflow()
    blog = ctx["blog"]
    editor = ctx["editor"]

    # 1. Submit for review runs first
    sub_res = client.post(
        f"/api/v1/blogs/{blog.id}/submit-for-review",
        headers=auth_header(editor),
    )
    assert sub_res.status_code == 201
    sub_data = sub_res.json()
    assert sub_data["submitted_revision_id"] == ctx["v0"].id

    # 2. Chat mutation attempts to execute while blog is PENDING_REVIEW
    chat_res = client.post(
        f"/api/v1/blogs/{blog.id}/chat",
        json={"message": "Attempting edit while pending review", "base_revision_id": ctx["v0"].id},
        headers=auth_header(editor),
    )
    # Must be blocked by mutation guard with 409
    assert chat_res.status_code == 409
    assert "pending_review" in chat_res.text.lower()

    # 3. Verify Outcome B invariant: no V1 revision created, review remains bound to V0
    db_session.expire_all()
    rev_count = db_session.query(BlogRevision).filter(BlogRevision.blog_id == blog.id).count()
    assert rev_count == 1
    latest_rev = (
        db_session.query(BlogRevision)
        .filter(BlogRevision.blog_id == blog.id)
        .order_by(BlogRevision.revision_number.desc())
        .first()
    )
    assert latest_rev.id == ctx["v0"].id
    assert sub_data["submitted_revision_id"] == latest_rev.id


def _create_isolated_concurrency_env(session: Session, suffix: str):
    """Helper creating committed DB records for multi-threaded test isolation."""
    comp = Company(
        name=f"Race Co {suffix}",
        description="Race Company",
        logo_url="https://example.com/logo.png",
        company_type="Private",
        industry="Technology",
        country_region="United States",
        company_email=f"race_{suffix}@example.com",
        notification_email=f"race_{suffix}@example.com",
    )
    session.add(comp)
    session.flush()

    editor = User(
        company_id=comp.id,
        name=f"Editor {suffix}",
        email=f"editor_{suffix}@example.com",
        password_hash=hash_password("StrongPassword123!"),
        role=UserRole.EDITOR,
        status=UserStatus.ACTIVE,
        permanent_password_set=True,
    )
    reviewer = User(
        company_id=comp.id,
        name=f"Reviewer {suffix}",
        email=f"reviewer_{suffix}@example.com",
        password_hash=hash_password("StrongPassword123!"),
        role=UserRole.REVIEWER,
        status=UserStatus.ACTIVE,
        permanent_password_set=True,
    )
    session.add_all([editor, reviewer])
    session.flush()

    topic = TopicCandidate(
        company_id=comp.id,
        title=f"Race Topic {suffix}",
        angle="Race Angle",
        primary_keyword="cloud observability",
        status=TopicStatus.SELECTED,
    )
    session.add(topic)
    session.flush()

    blog_format = BlogFormat(
        company_id=comp.id,
        format_definition="Standard company blog format with introduction and conclusion.",
        version=1,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    session.add(blog_format)
    session.flush()

    draft = create_valid_test_draft("cloud observability")
    blog = Blog(
        company_id=comp.id,
        topic_candidate_id=topic.id,
        created_by_user_id=editor.id,
        title=draft.h1_title,
        slug=f"race-blog-{suffix}",
        primary_keyword=draft.primary_keyword,
        seo_title=draft.seo_title,
        meta_description=draft.meta_description,
        content_json=draft.model_dump(),
        content_markdown=render_blog_to_markdown(draft),
        status=BlogStatus.DRAFT,
        format_version=1,
        generation_metadata={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(blog)
    session.flush()

    rev_svc = BlogRevisionService(db=session)
    v0 = rev_svc.ensure_initial_revision_v0(blog=blog, editor_id=editor.id)
    session.commit()

    return {
        "company": comp,
        "editor": editor,
        "reviewer": reviewer,
        "blog": blog,
        "v0": v0,
    }


def test_def_p9_01_concurrent_race_impossible_state_prevented():
    """
    Deterministic race test: Thread A (POST /chat) vs Thread B (POST /submit-for-review).
    Verifies that the mixed/impossible state:
        Review submitted_revision_id == V0 while Blog current/latest revision == V1
    NEVER occurs under concurrent execution.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from backend.app.core.database import engine, get_db
    from backend.main import app

    # Remove dependency overrides so each request gets its own real DB session & transaction
    saved_overrides = dict(app.dependency_overrides)
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]

    client = TestClient(app)

    try:
        with Session(engine) as session:
            suffix = uuid.uuid4().hex[:8]
            ctx = _create_isolated_concurrency_env(session, suffix)
            blog_id = ctx["blog"].id
            editor = ctx["editor"]
            v0_id = ctx["v0"].id

            barrier = threading.Barrier(2)

            def do_chat():
                barrier.wait()
                return client.post(
                    f"/api/v1/blogs/{blog_id}/chat",
                    json={"message": "Please refine the introduction section", "base_revision_id": v0_id},
                    headers=auth_header(editor),
                )

            def do_submit():
                barrier.wait()
                return client.post(
                    f"/api/v1/blogs/{blog_id}/submit-for-review",
                    headers=auth_header(editor),
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                f_chat = executor.submit(do_chat)
                f_sub = executor.submit(do_submit)
                res_chat = f_chat.result()
                res_sub = f_sub.result()

            # Refresh and inspect final DB state
            session.expire_all()
            final_blog = session.query(Blog).get(blog_id)
            latest_rev = (
                session.query(BlogRevision)
                .filter(BlogRevision.blog_id == blog_id)
                .order_by(BlogRevision.revision_number.desc())
                .first()
            )
            review = (
                session.query(BlogReview)
                .filter(BlogReview.blog_id == blog_id)
                .order_by(BlogReview.id.desc())
                .first()
            )

            # Must satisfy strictly Outcome A or Outcome B:
            if res_chat.status_code == 200:
                # Outcome A: Chat won first
                assert res_sub.status_code == 201
                assert latest_rev.revision_number == 1
                assert review is not None
                assert review.submitted_revision_id == latest_rev.id
            else:
                # Outcome B: Submit won first
                assert res_sub.status_code == 201
                assert res_chat.status_code == 409
                assert latest_rev.revision_number == 0
                assert review is not None
                assert review.submitted_revision_id == latest_rev.id

            # CRITICAL INVARIANT: The impossible state must never exist
            assert review.submitted_revision_id == latest_rev.id
            assert not (review.submitted_revision_id == v0_id and latest_rev.revision_number == 1)

            # Teardown
            session.query(BlogReview).filter(BlogReview.blog_id == blog_id).delete(synchronize_session=False)
            thread_ids = [t.id for t in session.query(BlogChatThread).filter(BlogChatThread.blog_id == blog_id).all()]
            if thread_ids:
                session.query(BlogChatMessage).filter(BlogChatMessage.thread_id.in_(thread_ids)).delete(synchronize_session=False)
            session.query(BlogChatThread).filter(BlogChatThread.blog_id == blog_id).delete(synchronize_session=False)
            session.query(BlogRevision).filter(BlogRevision.blog_id == blog_id).delete(synchronize_session=False)
            session.query(Blog).filter(Blog.id == blog_id).delete(synchronize_session=False)
            session.query(TopicCandidate).filter(TopicCandidate.company_id == ctx["company"].id).delete(synchronize_session=False)
            session.query(BlogFormat).filter(BlogFormat.company_id == ctx["company"].id).delete(synchronize_session=False)
            session.query(User).filter(User.company_id == ctx["company"].id).delete(synchronize_session=False)
            session.query(Company).filter(Company.id == ctx["company"].id).delete(synchronize_session=False)
            session.commit()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved_overrides)


def test_def_p9_01_concurrent_race_repeated_no_duplicates_no_partial_revisions():
    """
    Repeats the race 5 times to stress test mutual exclusion and verify:
    1. No duplicate review rows.
    2. No partial or corrupted BlogRevision rows.
    3. Impossible state never occurs in any execution.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from backend.app.core.database import engine, get_db
    from backend.main import app

    saved_overrides = dict(app.dependency_overrides)
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]

    client = TestClient(app)

    try:
        for iteration in range(5):
            with Session(engine) as session:
                suffix = f"rep-{iteration}-{uuid.uuid4().hex[:6]}"
                ctx = _create_isolated_concurrency_env(session, suffix)
                blog_id = ctx["blog"].id
                editor = ctx["editor"]
                v0_id = ctx["v0"].id

                barrier = threading.Barrier(2)

                def do_chat():
                    barrier.wait()
                    return client.post(
                        f"/api/v1/blogs/{blog_id}/chat",
                        json={"message": f"Please refine the introduction section for iteration {iteration}", "base_revision_id": v0_id},
                        headers=auth_header(editor),
                    )

                def do_submit():
                    barrier.wait()
                    return client.post(
                        f"/api/v1/blogs/{blog_id}/submit-for-review",
                        headers=auth_header(editor),
                    )

                with ThreadPoolExecutor(max_workers=2) as executor:
                    f_chat = executor.submit(do_chat)
                    f_sub = executor.submit(do_submit)
                    res_chat = f_chat.result()
                    res_sub = f_sub.result()

                assert res_sub.status_code == 201, f"Submit failed with {res_sub.status_code}: {res_sub.text}. Chat returned: {res_chat.status_code}: {res_chat.text}"

                session.expire_all()
                reviews = session.query(BlogReview).filter(BlogReview.blog_id == blog_id).all()
                revisions = (
                    session.query(BlogRevision)
                    .filter(BlogRevision.blog_id == blog_id)
                    .order_by(BlogRevision.revision_number.asc())
                    .all()
                )
                latest_rev = revisions[-1]

                # 1. No duplicate review rows
                assert len(reviews) == 1, f"Expected exactly 1 review row, found {len(reviews)}"
                review = reviews[0]

                # 2. No partial BlogRevision rows
                for rev in revisions:
                    assert rev.revision_number is not None
                    assert rev.revision_summary is not None
                    assert rev.content_json is not None
                    assert "h1_title" in rev.content_json
                    assert rev.content_markdown is not None
                    assert len(rev.content_markdown) > 0

                # 3. Invariant check: review binds latest revision
                assert review.submitted_revision_id == latest_rev.id
                assert not (review.submitted_revision_id == v0_id and latest_rev.revision_number == 1)

                # Valid outcome check
                if res_chat.status_code == 200:
                    assert res_sub.status_code == 201
                    assert latest_rev.revision_number == 1
                else:
                    assert res_sub.status_code == 201
                    assert res_chat.status_code == 409
                    assert latest_rev.revision_number == 0

                # Teardown iteration records
                session.query(BlogReview).filter(BlogReview.blog_id == blog_id).delete(synchronize_session=False)
                thread_ids = [t.id for t in session.query(BlogChatThread).filter(BlogChatThread.blog_id == blog_id).all()]
                if thread_ids:
                    session.query(BlogChatMessage).filter(BlogChatMessage.thread_id.in_(thread_ids)).delete(synchronize_session=False)
                session.query(BlogChatThread).filter(BlogChatThread.blog_id == blog_id).delete(synchronize_session=False)
                session.query(BlogRevision).filter(BlogRevision.blog_id == blog_id).delete(synchronize_session=False)
                session.query(Blog).filter(Blog.id == blog_id).delete(synchronize_session=False)
                session.query(TopicCandidate).filter(TopicCandidate.company_id == ctx["company"].id).delete(synchronize_session=False)
                session.query(BlogFormat).filter(BlogFormat.company_id == ctx["company"].id).delete(synchronize_session=False)
                session.query(User).filter(User.company_id == ctx["company"].id).delete(synchronize_session=False)
                session.query(Company).filter(Company.id == ctx["company"].id).delete(synchronize_session=False)
                session.commit()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved_overrides)


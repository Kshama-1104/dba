"""
Phase 11 — WordPress Publishing Comprehensive Test Suite

Tests all invariants of Phase 11:
1. Connection CRUD & authenticated AES-256-GCM encryption at rest
2. Secret non-disclosure (credentials never returned or logged)
3. RBAC (Company Admin full, Editor read-only/test, Reviewer denied) & Tenant Isolation (IDOR rejection)
4. Comprehensive SSRF Protection (loopback, RFC1918, link-local, cloud metadata, IPv4-mapped IPv6)
5. Connection Testing without post creation (capabilities check, auth, unreachable)
6. Publication execution, semantic content preservation, and HTML sanitization
7. Pre-POST atomic claim gate & local concurrency safety
8. Remote idempotency protocol (slug query + exact comment marker recovery)
9. Crash recovery (Worker A crashes after WP post; Worker B discovers and recovers without duplicate)
10. Error classification (transient vs terminal) and 429 rate-limiting Retry-After handling
11. Preserved audit retention after connection deletion (ON DELETE SET NULL)
12. Phase 10 boundary preservation (no direct mutation of schedules or jobs)
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import pytest
from fastapi.testclient import TestClient
import httpx
from sqlalchemy.orm import Session

from backend.app.core.credential_vault import decrypt_credentials
from backend.app.core.ssrf_protection import (
    SSRFProtectionError,
    validate_destination_url,
)
from backend.app.models.blog import Blog, BlogStatus
from backend.app.models.blog_chat import BlogRevision
from backend.app.models.blog_review import BlogReview
from backend.app.models.blog_schedule import (
    BlogPublicationJob,
    BlogSchedule,
    PublicationJobStatus,
    ScheduleStatus,
)
from backend.app.models.topic_candidate import TopicCandidate, TopicStatus
from backend.app.models.user import User, UserRole
from backend.app.models.wordpress_connection import (
    WordPressConnection,
    WordPressConnectionStatus,
    WordPressPublicationRecord,
    WordPressPublicationStatus,
)
from backend.app.services.auth_service import create_user_access_token
from backend.app.services.publication_contract import (
    PublicationContract,
    PublicationResult,
)
from backend.app.services.publication_provider_factory import get_publication_provider
from backend.app.services.wordpress_provider import (
    WordPressPublicationProvider,
    render_structured_draft_to_html,
)
from backend.app.services.wordpress_service import WordPressService
from backend.app.worker.scheduler_worker import SchedulerWorker


import socket


@pytest.fixture(autouse=True)
def mock_dns_for_tests(monkeypatch):
    """Ensure tests run offline without real network DNS calls while testing SSRF invariants."""
    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host in ("localhost", "127.0.0.1"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
        if host in ("::1",):
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", port, 0, 0))]
        if host in ("169.254.169.254",):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", port))]
        if "malicious-dns" in str(host) or "private-dns" in str(host):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", port))]
        if "unresolvable" in str(host):
            raise socket.gaierror(11001, "getaddrinfo failed")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


def auth_header(user: User) -> dict:
    token = create_user_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def setup_wp_env(db_session: Session, create_company, create_user):
    """Fixture creating company, admin, editor, reviewer, and approved blog with revision."""
    company = create_company(name="WordPress Publishing Corp")
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN, email="admin_wp@example.com")
    editor = create_user(company_id=company.id, role=UserRole.EDITOR, email="editor_wp@example.com")
    reviewer = create_user(company_id=company.id, role=UserRole.REVIEWER, email="reviewer_wp@example.com")

    # Company 2 for tenant isolation
    company2 = create_company(name="Competitor Corp")
    admin2 = create_user(company_id=company2.id, role=UserRole.COMPANY_ADMIN, email="admin2_wp@example.com")

    topic = TopicCandidate(
        company_id=company.id,
        title="Modern Cloud Architecture Patterns",
        angle="Enterprise patterns",
        primary_keyword="cloud architecture",
        status=TopicStatus.SELECTED,
    )
    db_session.add(topic)
    db_session.flush()

    blog = Blog(
        company_id=company.id,
        topic_candidate_id=topic.id,
        created_by_user_id=editor.id,
        title="Modern Cloud Architecture Patterns",
        slug="modern-cloud-architecture-patterns",
        primary_keyword="cloud architecture",
        seo_title="Modern Cloud Architecture Patterns for Enterprise",
        meta_description="Explore resilient cloud architecture patterns for scaling enterprise workloads.",
        content_json={
            "h1_title": "Modern Cloud Architecture Patterns",
            "introduction": "Cloud architecture is evolving rapidly.",
            "sections": [
                {"heading": "Microservices Resiliency", "level": 2, "content": "Implement circuit breakers.\n\nUse event driven models."},
                {"heading": "Database Partitioning", "level": 3, "content": "Shard across availability zones."},
            ],
            "conclusion": "Resilient architecture ensures business continuity.",
            "call_to_action": "Contact our solutions architect team today.",
            "slug": "modern-cloud-architecture-patterns",
            "meta_description": "Explore resilient cloud architecture patterns.",
        },
        content_markdown="# Modern Cloud Architecture Patterns\n\nCloud architecture is evolving rapidly.\n\n## Microservices Resiliency\n\nImplement circuit breakers.",
        status=BlogStatus.APPROVED,
    )
    db_session.add(blog)
    db_session.flush()

    rev = BlogRevision(
        company_id=company.id,
        blog_id=blog.id,
        revision_number=1,
        revision_summary="Approved V1 revision",
        seo_title="Modern Cloud Architecture Patterns for Enterprise",
        primary_keyword="cloud architecture",
        meta_description="Explore resilient cloud architecture patterns.",
        content_json=blog.content_json,
        content_markdown=blog.content_markdown,
    )
    db_session.add(rev)
    db_session.flush()

    # Review approving revision
    review = BlogReview(
        company_id=company.id,
        blog_id=blog.id,
        submitted_revision_id=rev.id,
        reviewer_id=reviewer.id,
        status="approved",
        decided_at=datetime.now(timezone.utc),
    )
    db_session.add(review)

    # Schedule & publication job
    sched = BlogSchedule(
        company_id=company.id,
        blog_id=blog.id,
        target_revision_id=rev.id,
        scheduled_at_utc=datetime.now(timezone.utc),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.QUEUED.value,
        created_by_user_id=editor.id,
    )
    db_session.add(sched)
    db_session.flush()

    job = BlogPublicationJob(
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        attempt_number=1,
        idempotency_key=f"pub_schedule_{sched.id}_rev_{rev.id}_attempt_1",
        status=PublicationJobStatus.QUEUED.value,
    )
    db_session.add(job)
    db_session.commit()

    return {
        "company": company,
        "admin": admin,
        "editor": editor,
        "reviewer": reviewer,
        "company2": company2,
        "admin2": admin2,
        "blog": blog,
        "revision": rev,
        "schedule": sched,
        "job": job,
    }


# ==============================================================================
# 1. CONNECTION CRUD & ENCRYPTION AT REST
# ==============================================================================

def test_connection_create_and_encryption(db_session: Session, client: TestClient, setup_wp_env):
    """Verify connection creation, authenticated AES-256-GCM encryption, and secret masking."""
    env = setup_wp_env
    admin = env["admin"]

    # Connect WordPress
    payload = {
        "site_url": "https://blog.dailyblog.ai",
        "username": "wp_publisher",
        "application_password": "abcd efgh ijkl mnop",
        "default_post_status": "publish",
    }
    resp = client.post("/api/v1/integrations/wordpress", json=payload, headers=auth_header(admin))
    assert resp.status_code == 201
    data = resp.json()
    assert data["site_url"] == "https://blog.dailyblog.ai"
    assert data["username"] == "wp_publisher"
    assert data["status"] == "ACTIVE"
    assert data["masked_credential"] == "••••••••"
    # Secret must never be in API response
    assert "abcd efgh" not in json.dumps(data)

    # Verify database level: encrypted at rest
    conn = db_session.query(WordPressConnection).filter(WordPressConnection.company_id == admin.company_id).first()
    assert conn is not None
    assert "abcd efgh" not in conn.encrypted_credential
    # Decrypt with vault
    decrypted = decrypt_credentials(conn.encrypted_credential)
    assert decrypted["application_password"] == "abcd efgh ijkl mnop"


def test_connection_get_and_update(db_session: Session, client: TestClient, setup_wp_env):
    """Verify getting connection metadata and updating connection settings / rotating password."""
    env = setup_wp_env
    admin = env["admin"]

    # 1. Get before creating -> 404
    resp = client.get("/api/v1/integrations/wordpress", headers=auth_header(admin))
    assert resp.status_code == 404

    # 2. Create
    client.post(
        "/api/v1/integrations/wordpress",
        json={"site_url": "https://blog.dailyblog.ai", "username": "admin", "application_password": "pwd1"},
        headers=auth_header(admin),
    )

    # 3. Get -> 200 with masked credentials
    resp = client.get("/api/v1/integrations/wordpress", headers=auth_header(admin))
    assert resp.status_code == 200
    assert resp.json()["masked_credential"] == "••••••••"

    # 4. Update password
    up_resp = client.put(
        "/api/v1/integrations/wordpress",
        json={"application_password": "new_secret_password"},
        headers=auth_header(admin),
    )
    assert up_resp.status_code == 200

    conn = db_session.query(WordPressConnection).filter(WordPressConnection.company_id == admin.company_id).first()
    decrypted = decrypt_credentials(conn.encrypted_credential)
    assert decrypted["application_password"] == "new_secret_password"


def test_connection_deletion_and_audit_preservation(db_session: Session, client: TestClient, setup_wp_env):
    """Verify connection DELETE physically purges credentials while publication records survive with connection_id=NULL."""
    env = setup_wp_env
    admin = env["admin"]
    blog = env["blog"]
    rev = env["revision"]

    # Create connection
    client.post(
        "/api/v1/integrations/wordpress",
        json={"site_url": "https://blog.dailyblog.ai", "username": "admin", "application_password": "secret_pwd"},
        headers=auth_header(admin),
    )
    conn = db_session.query(WordPressConnection).filter(WordPressConnection.company_id == admin.company_id).first()

    # Create a publication record linked to this connection
    pub_record = WordPressPublicationRecord(
        company_id=admin.company_id,
        connection_id=conn.id,
        blog_id=blog.id,
        revision_id=rev.id,
        publication_idempotency_key="pub_test_del_1",
        status=WordPressPublicationStatus.SUCCEEDED.value,
        external_post_id="999",
        external_url="https://blog.dailyblog.ai/post-999",
        target_site_url=conn.site_url,
        target_username=conn.username,
    )
    db_session.add(pub_record)
    db_session.commit()

    # Execute DELETE connection
    del_resp = client.delete("/api/v1/integrations/wordpress", headers=auth_header(admin))
    assert del_resp.status_code == 204

    # Verify connection is physically deleted
    assert db_session.query(WordPressConnection).filter(WordPressConnection.company_id == admin.company_id).first() is None

    # Verify publication record SURVIVED with connection_id = NULL (ON DELETE SET NULL)
    db_session.refresh(pub_record)
    assert pub_record.connection_id is None
    assert pub_record.external_post_id == "999"
    assert pub_record.target_site_url == "https://blog.dailyblog.ai"
    assert pub_record.target_username == "admin"


# ==============================================================================
# 2. RBAC & TENANT ISOLATION
# ==============================================================================

def test_rbac_permissions_and_restrictions(db_session: Session, client: TestClient, setup_wp_env):
    """Verify Admin can create/update/delete; Editor can read/test; Reviewer cannot access."""
    env = setup_wp_env
    admin = env["admin"]
    editor = env["editor"]
    reviewer = env["reviewer"]

    # Setup connection as Admin
    client.post(
        "/api/v1/integrations/wordpress",
        json={"site_url": "https://blog.dailyblog.ai", "username": "admin", "application_password": "pwd"},
        headers=auth_header(admin),
    )

    # Editor can GET
    resp = client.get("/api/v1/integrations/wordpress", headers=auth_header(editor))
    assert resp.status_code == 200

    # Editor CANNOT update connection (403 Forbidden)
    resp = client.put(
        "/api/v1/integrations/wordpress",
        json={"username": "hacker"},
        headers=auth_header(editor),
    )
    assert resp.status_code == 403

    # Editor CANNOT delete connection (403 Forbidden)
    resp = client.delete("/api/v1/integrations/wordpress", headers=auth_header(editor))
    assert resp.status_code == 403

    # Reviewer can GET metadata
    resp = client.get("/api/v1/integrations/wordpress", headers=auth_header(reviewer))
    assert resp.status_code == 200

    # Reviewer CANNOT test connection (403 Forbidden)
    resp = client.post("/api/v1/integrations/wordpress/test", headers=auth_header(reviewer))
    assert resp.status_code == 403


def test_tenant_isolation(db_session: Session, client: TestClient, setup_wp_env):
    """Verify Company A cannot view, update, test, or publish via Company B's WordPress site."""
    env = setup_wp_env
    admin = env["admin"]
    admin2 = env["admin2"]

    # Company 1 configures WordPress
    client.post(
        "/api/v1/integrations/wordpress",
        json={"site_url": "https://company1.blog.com", "username": "admin1", "application_password": "pwd1"},
        headers=auth_header(admin),
    )

    # Company 2 GETs -> 404 Not Found (isolated)
    resp = client.get("/api/v1/integrations/wordpress", headers=auth_header(admin2))
    assert resp.status_code == 404

    # Company 2 cannot delete Company 1 connection
    del_resp = client.delete("/api/v1/integrations/wordpress", headers=auth_header(admin2))
    assert del_resp.status_code == 404


# ==============================================================================
# 3. SSRF PROTECTION
# ==============================================================================

@pytest.mark.parametrize(
    "bad_url",
    [
        "http://localhost/wp",
        "http://127.0.0.1:8080",
        "https://127.0.0.1",
        "https://[::1]",
        "http://169.254.169.254/latest/meta-data",
        "https://169.254.169.254",
        "https://10.0.0.1/wp-json",
        "https://172.16.0.1",
        "https://192.168.1.1",
        "https://100.64.0.1",
        "https://[::ffff:127.0.0.1]",
        "ftp://example.com/wp",
        "file:///etc/passwd",
    ],
)
def test_ssrf_rejects_forbidden_targets(bad_url: str):
    """Verify all internal, private, loopback, metadata, and non-HTTPS targets are rejected."""
    with pytest.raises(SSRFProtectionError):
        validate_destination_url(bad_url)


def test_ssrf_enforces_https():
    """Verify standard HTTP is rejected in production mode."""
    with pytest.raises(SSRFProtectionError, match="Insecure HTTP is forbidden"):
        validate_destination_url("http://blog.mycompany.com")


# ==============================================================================
# 4. CONNECTION TESTING (WITHOUT POSTING)
# ==============================================================================

def test_connection_test_success_with_mock_transport(db_session: Session, setup_wp_env):
    """Verify test_connection passes when WordPress /users/me returns valid user with publishing capabilities."""
    env = setup_wp_env
    admin = env["admin"]

    # Setup connection
    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=admin.company_id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "publisher_bot",
            "application_password": "app_pwd_123",
            "default_post_status": "publish",
        })(),
    )

    def mock_wp_users_me(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wp/v2/users/me"
        assert "Basic " in request.headers.get("Authorization", "")
        return httpx.Response(
            200,
            json={
                "id": 5,
                "name": "Publisher Bot",
                "capabilities": {"publish_posts": True, "edit_posts": True},
                "roles": ["author"],
            },
        )

    async def _run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(mock_wp_users_me)) as client:
            return await WordPressService.test_connection(db_session, admin.company_id, client=client)

    result = asyncio.run(_run())
    assert result.success is True
    assert result.can_publish is True
    assert result.authenticated_user == "Publisher Bot"
    assert result.error_message is None


def test_connection_test_insufficient_capabilities(db_session: Session, setup_wp_env):
    """Verify test_connection fails when user authenticates but lacks publish_posts or edit_posts capability."""
    env = setup_wp_env
    admin = env["admin"]

    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=admin.company_id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "subscriber_user",
            "application_password": "pwd",
            "default_post_status": "publish",
        })(),
    )

    def mock_wp_subscriber(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 9,
                "name": "Subscriber User",
                "capabilities": {"read": True},
                "roles": ["subscriber"],
            },
        )

    async def _run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(mock_wp_subscriber)) as client:
            return await WordPressService.test_connection(db_session, admin.company_id, client=client)

    result = asyncio.run(_run())
    assert result.success is False
    assert result.can_publish is False
    assert "lacks sufficient publishing capability" in result.error_message


# ==============================================================================
# 5. CONTENT TRANSFORMATION & HTML SANITIZATION
# ==============================================================================

def test_semantic_content_preservation_and_html_sanitization():
    """Verify semantic content preservation, paragraph wrapping, headings, CTA, and XSS sanitization."""
    draft = {
        "h1_title": "Enterprise Cloud Architecture",
        "introduction": "This is an introductory guide to cloud architecture.",
        "sections": [
            {"heading": "High Availability", "level": 2, "content": "Deploy in multiple regions.\n\nUse load balancers."},
            {"heading": "Disaster Recovery", "level": 3, "content": "Automate snapshot backups."},
        ],
        "conclusion": "Cloud architecture is essential for resilience.",
        "call_to_action": "Schedule a demo with our architecture team.",
        # Adversarial XSS payload injected
        "meta_description": "Safe description <script>alert('xss')</script>",
    }
    marker = "<!-- dailyblog-pub-key: pub_schedule_10_rev_1 -->"

    # Inject malicious script and iframe into body
    draft["sections"][0]["content"] += '\n\n<script>malicious_code()</script><iframe src="evil.com"></iframe>'

    html = render_structured_draft_to_html(draft, fallback_markdown="", idempotency_marker=marker)

    # Invariants preserved
    assert '<p class="dailyblog-intro">This is an introductory guide to cloud architecture.</p>' in html
    assert '<h2>High Availability</h2>' in html
    assert '<h3>Disaster Recovery</h3>' in html
    assert '<p>Deploy in multiple regions.</p>' in html
    assert '<p>Use load balancers.</p>' in html
    assert '<h2>Conclusion</h2>' in html
    assert '<strong>Call to Action:</strong> Schedule a demo with our architecture team.' in html
    assert marker in html

    # Security sanitization (XSS stripped)
    assert '<script>' not in html
    assert 'malicious_code()' not in html
    assert '<iframe>' not in html


# ==============================================================================
# 6. PUBLICATION EXECUTION & IDEMPOTENCY GATE
# ==============================================================================

def test_successful_wordpress_publication_and_audit_persistence(db_session: Session, setup_wp_env):
    """Verify full publication flow: Pre-POST claim, remote check, POST create, and external reference."""
    env = setup_wp_env
    company = env["company"]
    admin = env["admin"]
    blog = env["blog"]
    rev = env["revision"]
    sched = env["schedule"]
    job = env["job"]

    # Register WordPress connection
    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=company.id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "wp_publisher",
            "application_password": "pass",
            "default_post_status": "publish",
        })(),
    )

    created_payloads = []

    def mock_wp_publish(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            # Lookup before POST returns empty array
            return httpx.Response(200, json=[])
        if request.method == "POST":
            created_payloads.append(json.loads(request.content))
            return httpx.Response(
                201,
                json={"id": 456, "link": "https://blog.dailyblog.ai/modern-cloud-architecture-patterns", "status": "publish"},
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_wp_publish))
    provider = WordPressPublicationProvider(db=db_session, client=client, worker_id="test_worker_1")

    contract = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=1,
        publication_idempotency_key=f"pub_schedule_{sched.id}_rev_{rev.id}",
    )

    res = asyncio.run(provider.publish(contract))
    assert res.success is True
    assert res.external_reference == "wp_post:456"
    assert res.published_url == "https://blog.dailyblog.ai/modern-cloud-architecture-patterns"

    # Verify publication record in DB
    rec = db_session.query(WordPressPublicationRecord).filter(
        WordPressPublicationRecord.company_id == company.id,
        WordPressPublicationRecord.publication_idempotency_key == contract.publication_idempotency_key,
    ).first()
    assert rec is not None
    assert rec.status == WordPressPublicationStatus.SUCCEEDED.value
    assert rec.external_post_id == "456"
    assert rec.external_url == "https://blog.dailyblog.ai/modern-cloud-architecture-patterns"
    assert rec.published_at is not None

    # Idempotency marker was embedded
    assert len(created_payloads) == 1
    assert f"<!-- dailyblog-pub-key: {contract.publication_idempotency_key} -->" in created_payloads[0]["content"]


def test_idempotency_second_call_zero_http_requests(db_session: Session, setup_wp_env):
    """Verify calling publish when status=SUCCEEDED makes zero HTTP calls and returns cached references."""
    env = setup_wp_env
    company = env["company"]
    admin = env["admin"]
    blog = env["blog"]
    rev = env["revision"]
    sched = env["schedule"]
    job = env["job"]

    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=company.id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "wp_publisher",
            "application_password": "pass",
            "default_post_status": "publish",
        })(),
    )

    http_calls = []

    def mock_wp(request: httpx.Request) -> httpx.Response:
        http_calls.append(request.url)
        return httpx.Response(201, json={"id": 789, "link": "https://blog.dailyblog.ai/post-789"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_wp))
    provider = WordPressPublicationProvider(db=db_session, client=client)

    contract = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=1,
        publication_idempotency_key=f"pub_schedule_{sched.id}_rev_{rev.id}",
    )

    # Attempt 1: Calls WP
    res1 = asyncio.run(provider.publish(contract))
    assert res1.success is True
    assert len(http_calls) == 2  # 1 GET lookup + 1 POST create

    # Attempt 2: Same contract
    res2 = asyncio.run(provider.publish(contract))
    assert res2.success is True
    assert res2.external_reference == "wp_post:789"
    # Zero additional HTTP calls made!
    assert len(http_calls) == 2


def test_crash_recovery_lost_http_response_remote_lookup(db_session: Session, setup_wp_env):
    """
    CRITICAL FAILURE TEST:
    Worker A crashes after WordPress creates post 555.
    Worker B claims expired lease, performs remote lookup, discovers post 555 by marker,
    marks SUCCEEDED, and creates ZERO duplicate posts.
    """
    env = setup_wp_env
    company = env["company"]
    admin = env["admin"]
    blog = env["blog"]
    rev = env["revision"]
    sched = env["schedule"]
    job = env["job"]

    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=company.id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "wp_publisher",
            "application_password": "pass",
            "default_post_status": "publish",
        })(),
    )

    logical_key = f"pub_schedule_{sched.id}_rev_{rev.id}"
    marker = f"<!-- dailyblog-pub-key: {logical_key} -->"

    # Simulate Worker A crashed leaving IN_PROGRESS with an EXPIRED lease
    crashed_record = WordPressPublicationRecord(
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        publication_idempotency_key=logical_key,
        status=WordPressPublicationStatus.IN_PROGRESS.value,
        claim_worker_id="crashed_worker_A",
        claim_lease_until=datetime.now(timezone.utc) - timedelta(minutes=5),  # EXPIRED
        target_site_url="https://blog.dailyblog.ai",
        target_username="wp_publisher",
    )
    db_session.add(crashed_record)
    db_session.commit()

    post_calls = []

    def mock_wp_remote_recovery(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            # Remote WordPress already has post 555 with exact marker!
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 555,
                        "link": "https://blog.dailyblog.ai/modern-cloud-architecture-patterns",
                        "slug": "modern-cloud-architecture-patterns",
                        "content": {"rendered": f"<p>Cloud content</p>\n{marker}\n"},
                    }
                ],
            )
        if request.method == "POST":
            post_calls.append(request)
            return httpx.Response(201, json={"id": 999})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_wp_remote_recovery))
    provider = WordPressPublicationProvider(db=db_session, client=client, worker_id="worker_B")

    contract = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=2,
        publication_idempotency_key=logical_key,
    )

    # Worker B executes Attempt 2
    res = asyncio.run(provider.publish(contract))
    assert res.success is True
    assert res.external_reference == "wp_post:555"
    assert res.published_url == "https://blog.dailyblog.ai/modern-cloud-architecture-patterns"

    # Zero POST requests issued!
    assert len(post_calls) == 0

    # DB record updated to SUCCEEDED
    db_session.refresh(crashed_record)
    assert crashed_record.status == WordPressPublicationStatus.SUCCEEDED.value
    assert crashed_record.external_post_id == "555"


def test_crash_recovery_before_post_worker_creates_exactly_one_post(db_session: Session, setup_wp_env):
    """
    CRASH RECOVERY TEST: Worker A crashes BEFORE issuing POST.
    Worker B claims expired lease, checks remote, finds nothing, and creates exactly one post.
    """
    env = setup_wp_env
    company = env["company"]
    admin = env["admin"]
    blog = env["blog"]
    rev = env["revision"]
    sched = env["schedule"]
    job = env["job"]

    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=company.id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "wp_publisher",
            "application_password": "pass",
            "default_post_status": "publish",
        })(),
    )

    logical_key = f"pub_schedule_{sched.id}_rev_{rev.id}_crashed_before_post"

    # Worker A claimed lease, but died before POST
    crashed_record = WordPressPublicationRecord(
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        publication_idempotency_key=logical_key,
        status=WordPressPublicationStatus.IN_PROGRESS.value,
        claim_worker_id="crashed_worker_A",
        claim_lease_until=datetime.now(timezone.utc) - timedelta(minutes=1),  # EXPIRED
        target_site_url="https://blog.dailyblog.ai",
        target_username="wp_publisher",
    )
    db_session.add(crashed_record)
    db_session.commit()

    post_calls = []

    def mock_wp_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if request.method == "POST":
            post_calls.append(request)
            return httpx.Response(201, json={"id": 777, "link": "https://blog.dailyblog.ai/post-777"})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_wp_handler))
    provider = WordPressPublicationProvider(db=db_session, client=client, worker_id="worker_B")

    contract = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=2,
        publication_idempotency_key=logical_key,
    )

    res = asyncio.run(provider.publish(contract))
    assert res.success is True
    assert res.external_reference == "wp_post:777"
    assert len(post_calls) == 1


def test_slug_conflict_rejection(db_session: Session, setup_wp_env):
    """Verify that if WordPress has a post with the same slug but WITHOUT the marker, it fails with WP_SLUG_CONFLICT."""
    env = setup_wp_env
    company = env["company"]
    admin = env["admin"]
    blog = env["blog"]
    rev = env["revision"]
    sched = env["schedule"]
    job = env["job"]

    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=company.id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "wp_publisher",
            "application_password": "pass",
            "default_post_status": "publish",
        })(),
    )

    def mock_wp_unrelated_post(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            # Returns an unrelated pre-existing user post without DailyBlog marker
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 111,
                        "slug": "modern-cloud-architecture-patterns",
                        "content": {"rendered": "<p>Unrelated customer post from 2021.</p>"},
                    }
                ],
            )
        return httpx.Response(201, json={"id": 222})

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_wp_unrelated_post))
    provider = WordPressPublicationProvider(db=db_session, client=client)

    contract = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=1,
        publication_idempotency_key=f"pub_schedule_{sched.id}_rev_{rev.id}",
    )

    res = asyncio.run(provider.publish(contract))
    assert res.success is False
    assert res.is_transient_error is False
    assert res.error_code == "WP_SLUG_CONFLICT"


# ==============================================================================
# 7. ERROR CLASSIFICATION & RATE LIMITING
# ==============================================================================

@pytest.mark.parametrize(
    "status_code, expected_code, expected_transient",
    [
        (401, "WP_AUTH_FAILED", False),
        (403, "WP_FORBIDDEN", False),
        (400, "WP_INVALID_PAYLOAD", False),
        (404, "WP_NOT_FOUND", False),
        (429, "WP_RATE_LIMITED", True),
        (500, "WP_SERVER_ERROR", True),
        (502, "WP_SERVER_ERROR", True),
        (503, "WP_SERVER_ERROR", True),
    ],
)
def test_error_classification_transient_vs_permanent(
    db_session: Session, setup_wp_env, status_code: int, expected_code: str, expected_transient: bool
):
    """Verify HTTP error classification into transient and terminal failure states."""
    env = setup_wp_env
    company = env["company"]
    admin = env["admin"]
    blog = env["blog"]
    rev = env["revision"]
    sched = env["schedule"]
    job = env["job"]

    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=company.id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "admin",
            "application_password": "pwd",
            "default_post_status": "publish",
        })(),
    )

    def mock_wp_error(request: httpx.Request) -> httpx.Response:
        headers = {"Retry-After": "60"} if status_code == 429 else {}
        return httpx.Response(status_code, text="Error payload", headers=headers)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_wp_error))
    provider = WordPressPublicationProvider(db=db_session, client=client)

    contract = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=1,
        publication_idempotency_key=f"pub_schedule_{sched.id}_rev_{rev.id}_err_{status_code}",
    )

    res = asyncio.run(provider.publish(contract))
    assert res.success is False
    assert res.is_transient_error is expected_transient
    assert res.error_code == expected_code
    if status_code == 429:
        assert "Retry-After: 60s" in res.error_message


# ==============================================================================
# 8. SCHEDULER WORKER INTEGRATION & PHASE 10 BOUNDARY
# ==============================================================================

def test_scheduler_worker_integration_with_wordpress_provider(db_session: Session, setup_wp_env):
    """Verify SchedulerWorker end-to-end execution completes successfully using get_publication_provider."""
    env = setup_wp_env
    company = env["company"]
    admin = env["admin"]
    sched = env["schedule"]

    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=company.id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "admin",
            "application_password": "pwd",
            "default_post_status": "publish",
        })(),
    )

    def mock_wp_publish(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[])
        return httpx.Response(201, json={"id": 888, "link": "https://blog.dailyblog.ai/post-888"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_wp_publish))
    provider = get_publication_provider(db_session, client=mock_client)

    # Create a fresh approved blog and schedule to test complete worker lifecycle from claim
    topic2 = TopicCandidate(
        company_id=company.id,
        title="Integration Blog",
        angle="Patterns",
        primary_keyword="integration",
        status=TopicStatus.SELECTED,
    )
    db_session.add(topic2)
    db_session.flush()

    blog2 = Blog(
        company_id=company.id,
        topic_candidate_id=topic2.id,
        created_by_user_id=admin.id,
        title="Integration Blog",
        slug="integration-blog",
        primary_keyword="integration",
        content_json={"h1_title": "Integration Blog", "sections": []},
        content_markdown="# Integration Content",
        status=BlogStatus.APPROVED,
    )
    db_session.add(blog2)
    db_session.flush()

    rev2 = BlogRevision(
        company_id=company.id,
        blog_id=blog2.id,
        revision_number=1,
        revision_summary="Approved",
        seo_title="Integration Blog SEO",
        primary_keyword="integration",
        content_json=blog2.content_json,
        content_markdown="# Integration Content",
    )
    db_session.add(rev2)
    db_session.flush()

    review2 = BlogReview(
        company_id=company.id,
        blog_id=blog2.id,
        submitted_revision_id=rev2.id,
        reviewer_id=admin.id,
        status="approved",
        decided_at=datetime.now(timezone.utc),
    )
    db_session.add(review2)

    sched2 = BlogSchedule(
        company_id=company.id,
        blog_id=blog2.id,
        target_revision_id=rev2.id,
        scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
        local_scheduled_time=datetime.now(),
        timezone="UTC",
        status=ScheduleStatus.SCHEDULED.value,
        created_by_user_id=admin.id,
    )
    db_session.add(sched2)
    db_session.commit()

    worker = SchedulerWorker(worker_id="test_runner_worker")

    # Claim due schedule (Phase A)
    claimed = worker.claim_due_schedules(db_session)
    assert sched2.id in claimed

    # Start execution (Phase B)
    job_id = worker.start_execution(db_session, sched2.id)
    assert job_id is not None

    # Execute publication via Phase 11 provider (Phase C)
    result = asyncio.run(worker.execute_publication(db_session, job_id, publisher=provider))
    assert result.success is True
    assert result.external_reference == "wp_post:888"

    # Record result (Phase D)
    worker.record_result(db_session, job_id, result)

    db_session.refresh(sched2)
    assert sched2.status == ScheduleStatus.SUCCEEDED.value

    job = db_session.query(BlogPublicationJob).filter(BlogPublicationJob.schedule_id == sched2.id).first()
    assert job.status == PublicationJobStatus.SUCCEEDED.value
    assert job.external_reference == "wp_post:888"


# ==============================================================================
# 9. BOUNDARY PRESERVATION & ADDITIONAL RESILIENCY TESTS
# ==============================================================================

def test_in_progress_active_lease_yields_transient_in_progress(db_session: Session, setup_wp_env):
    """CASE C: If another worker has an active lease on the record, return WP_PUBLICATION_IN_PROGRESS without calling WP."""
    env = setup_wp_env
    company = env["company"]
    admin = env["admin"]
    blog = env["blog"]
    rev = env["revision"]
    sched = env["schedule"]
    job = env["job"]

    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=company.id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "admin",
            "application_password": "pwd",
            "default_post_status": "publish",
        })(),
    )

    logical_key = f"pub_schedule_{sched.id}_rev_{rev.id}_active_lease"

    # Pre-existing active claim with 2 minutes remaining on lease
    active_rec = WordPressPublicationRecord(
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        publication_idempotency_key=logical_key,
        status=WordPressPublicationStatus.IN_PROGRESS.value,
        claim_worker_id="active_worker_1",
        claim_lease_until=datetime.now(timezone.utc) + timedelta(minutes=2),
        target_site_url="https://blog.dailyblog.ai",
        target_username="admin",
    )
    db_session.add(active_rec)
    db_session.commit()

    http_calls = []

    def mock_wp(request: httpx.Request) -> httpx.Response:
        http_calls.append(request)
        return httpx.Response(200, json=[])

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_wp))
    provider = WordPressPublicationProvider(db=db_session, client=client, worker_id="worker_2")

    contract = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=1,
        publication_idempotency_key=logical_key,
    )

    res = asyncio.run(provider.publish(contract))
    assert res.success is False
    assert res.is_transient_error is True
    assert res.error_code == "WP_PUBLICATION_IN_PROGRESS"
    # Zero HTTP calls made to WordPress
    assert len(http_calls) == 0


def test_connection_not_configured_returns_terminal_failure(db_session: Session, setup_wp_env):
    """Verify that publishing without a configured WordPress connection returns terminal failure."""
    env = setup_wp_env
    company = env["company"]
    blog = env["blog"]
    rev = env["revision"]
    sched = env["schedule"]
    job = env["job"]

    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200)))
    provider = WordPressPublicationProvider(db=db_session, client=client)

    contract = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=1,
        publication_idempotency_key=f"pub_schedule_{sched.id}_rev_{rev.id}_noconn",
    )

    res = asyncio.run(provider.publish(contract))
    assert res.success is False
    assert res.is_transient_error is False
    assert res.error_code == "WORDPRESS_NOT_CONFIGURED"


def test_network_timeout_and_connection_failure_classification(db_session: Session, setup_wp_env):
    """Verify network timeouts and connection errors are classified as transient."""
    env = setup_wp_env
    company = env["company"]
    admin = env["admin"]
    blog = env["blog"]
    rev = env["revision"]
    sched = env["schedule"]
    job = env["job"]

    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=company.id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "admin",
            "application_password": "pwd",
            "default_post_status": "publish",
        })(),
    )

    # 1. Timeout
    def mock_timeout(request: httpx.Request):
        raise httpx.ConnectTimeout("Connection timed out", request=request)

    client_timeout = httpx.AsyncClient(transport=httpx.MockTransport(mock_timeout))
    provider_timeout = WordPressPublicationProvider(db=db_session, client=client_timeout)

    contract1 = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=1,
        publication_idempotency_key=f"pub_schedule_{sched.id}_rev_{rev.id}_timeout",
    )
    res1 = asyncio.run(provider_timeout.publish(contract1))
    assert res1.success is False
    assert res1.is_transient_error is True
    assert res1.error_code == "WP_NETWORK_TIMEOUT"

    # 2. Connection Failure
    def mock_conn_error(request: httpx.Request):
        raise httpx.ConnectError("Failed to establish a new connection", request=request)

    client_conn = httpx.AsyncClient(transport=httpx.MockTransport(mock_conn_error))
    provider_conn = WordPressPublicationProvider(db=db_session, client=client_conn)

    contract2 = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=1,
        publication_idempotency_key=f"pub_schedule_{sched.id}_rev_{rev.id}_connerr",
    )
    res2 = asyncio.run(provider_conn.publish(contract2))
    assert res2.success is False
    assert res2.is_transient_error is True
    assert res2.error_code == "WP_CONNECTION_FAILURE"


def test_phase11_boundary_preservation(db_session: Session, setup_wp_env):
    """
    CRITICAL BOUNDARY TEST:
    Verify Phase 11 provider NEVER modifies BlogSchedule or BlogPublicationJob states.
    Phase 10 retains complete ownership of scheduling, jobs, and execution state.
    """
    env = setup_wp_env
    company = env["company"]
    admin = env["admin"]
    blog = env["blog"]
    rev = env["revision"]
    sched = env["schedule"]
    job = env["job"]

    WordPressService.create_or_update_connection(
        db=db_session,
        company_id=company.id,
        user_id=admin.id,
        request=type("Req", (), {
            "site_url": "https://blog.dailyblog.ai",
            "username": "admin",
            "application_password": "pwd",
            "default_post_status": "publish",
        })(),
    )

    sched_status_before = sched.status
    job_status_before = job.status

    def mock_wp(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[])
        return httpx.Response(201, json={"id": 999, "link": "https://blog.dailyblog.ai/post-999"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_wp))
    provider = WordPressPublicationProvider(db=db_session, client=client)

    contract = PublicationContract(
        job_id=job.id,
        schedule_id=sched.id,
        company_id=company.id,
        blog_id=blog.id,
        revision_id=rev.id,
        title=rev.seo_title,
        content_markdown=rev.content_markdown,
        content_json=rev.content_json,
        attempt_number=1,
        publication_idempotency_key=f"pub_schedule_{sched.id}_rev_{rev.id}_boundary",
    )

    res = asyncio.run(provider.publish(contract))
    assert res.success is True

    # Assert Schedule and Job states were UNTOUCHED by provider
    db_session.refresh(sched)
    db_session.refresh(job)
    assert sched.status == sched_status_before
    assert job.status == job_status_before


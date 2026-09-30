from fastapi.testclient import TestClient

from backend.app.models.user import UserRole
from backend.app.services.company_ai_profile_service import (
    create_or_update_company_ai_profile,
)


def test_get_ai_profile_not_found(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    GET /api/v1/company/ai-profile returns 404 when no profile has been created yet.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    headers = auth_headers(admin)

    response = client.get("/api/v1/company/ai-profile", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Company AI profile not found."


def test_put_ai_profile_creates_profile(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    PUT /api/v1/company/ai-profile by Company Admin creates the profile when none exists.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    headers = auth_headers(admin)

    payload = {
        "products_services": "AI Automated Blogging",
        "target_audience": "B2B Marketing Managers",
        "preferred_writing_style": "Engaging and authoritative",
        "brand_voice": "Professional, visionary, articulate",
        "marketing_goals": "Increase organic search traffic",
        "company_guidelines": "Ensure all claims have technical proof",
        "upcoming_projects": "V2 Automated Scheduling",
        "partner_companies": "WordPress VIP, HubSpot",
        "achievements": "100k Monthly Readers",
    }

    response = client.put(
        "/api/v1/company/ai-profile",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] is not None
    assert data["company_id"] == company.id
    assert data["products_services"] == "AI Automated Blogging"
    assert data["brand_voice"] == "Professional, visionary, articulate"
    assert data["marketing_goals"] == "Increase organic search traffic"
    assert data["achievements"] == "100k Monthly Readers"
    assert "created_at" in data
    assert "updated_at" in data


def test_get_ai_profile_after_creation(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    GET /api/v1/company/ai-profile successfully returns the profile after creation.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    headers = auth_headers(admin)

    create_payload = {
        "brand_voice": "Thought-leader, analytical",
        "target_audience": "Fintech Developers",
    }
    client.put("/api/v1/company/ai-profile", headers=headers, json=create_payload)

    response = client.get("/api/v1/company/ai-profile", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["company_id"] == company.id
    assert data["brand_voice"] == "Thought-leader, analytical"
    assert data["target_audience"] == "Fintech Developers"


def test_put_ai_profile_updates_existing(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    PUT /api/v1/company/ai-profile updates an existing profile and persists modifications.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    headers = auth_headers(admin)

    initial_payload = {
        "brand_voice": "Friendly",
        "products_services": "Daily Blog AI",
    }
    res_init = client.put("/api/v1/company/ai-profile", headers=headers, json=initial_payload)
    profile_id = res_init.json()["id"]

    update_payload = {
        "brand_voice": "Bold and Direct",
        "marketing_goals": "Expand Global Reach",
    }
    res_update = client.put("/api/v1/company/ai-profile", headers=headers, json=update_payload)
    assert res_update.status_code == 200
    updated_data = res_update.json()

    assert updated_data["id"] == profile_id
    assert updated_data["brand_voice"] == "Bold and Direct"
    assert updated_data["marketing_goals"] == "Expand Global Reach"
    assert updated_data["products_services"] == "Daily Blog AI"  # Preserved


def test_reviewer_and_editor_read_access(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session,
):
    """
    Document 1 Permission Matrix:
    Reviewers and Editors have Read-Only access to Brand Voice / Company AI Context.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    reviewer = create_user(company_id=company.id, role=UserRole.REVIEWER)
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)

    # Admin populates profile
    create_or_update_company_ai_profile(
        db=db_session,
        company_id=company.id,
        profile_in={"brand_voice": "Corporate Excellence"},
    )

    # Reviewer can GET
    rev_res = client.get(
        "/api/v1/company/ai-profile",
        headers=auth_headers(reviewer),
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["brand_voice"] == "Corporate Excellence"

    # Editor can GET
    ed_res = client.get(
        "/api/v1/company/ai-profile",
        headers=auth_headers(editor),
    )
    assert ed_res.status_code == 200
    assert ed_res.json()["brand_voice"] == "Corporate Excellence"


def test_reviewer_and_editor_cannot_modify_ai_profile(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    Document 1 Permission Matrix:
    Only Company Admin can modify Company Profile & Brand Voice.
    Reviewers and Editors calling PUT /api/v1/company/ai-profile must receive 403 Forbidden.
    """
    company = create_company()
    reviewer = create_user(company_id=company.id, role=UserRole.REVIEWER)
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)

    modify_payload = {"brand_voice": "Hacked Voice"}

    # Reviewer fails PUT with 403
    rev_res = client.put(
        "/api/v1/company/ai-profile",
        headers=auth_headers(reviewer),
        json=modify_payload,
    )
    assert rev_res.status_code == 403
    assert "permission" in rev_res.json()["detail"].lower()

    # Editor fails PUT with 403
    ed_res = client.put(
        "/api/v1/company/ai-profile",
        headers=auth_headers(editor),
        json=modify_payload,
    )
    assert ed_res.status_code == 403
    assert "permission" in ed_res.json()["detail"].lower()


def test_tenant_isolation_get_and_put(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session,
):
    """
    Tenant Isolation Guarantee:
    Company A user cannot view or modify Company B's AI profile.
    All data is strictly derived from the authenticated token's company_id.
    """
    company_a = create_company(name="Alpha Corp")
    company_b = create_company(name="Beta Corp")

    admin_a = create_user(company_id=company_a.id, role=UserRole.COMPANY_ADMIN)
    admin_b = create_user(company_id=company_b.id, role=UserRole.COMPANY_ADMIN)

    # Alpha creates profile
    client.put(
        "/api/v1/company/ai-profile",
        headers=auth_headers(admin_a),
        json={"brand_voice": "Alpha Voice", "target_audience": "Alpha Audience"},
    )

    # Beta creates profile
    client.put(
        "/api/v1/company/ai-profile",
        headers=auth_headers(admin_b),
        json={"brand_voice": "Beta Voice", "target_audience": "Beta Audience"},
    )

    # Admin A reads profile -> receives Alpha, NOT Beta
    res_a = client.get("/api/v1/company/ai-profile", headers=auth_headers(admin_a))
    assert res_a.status_code == 200
    assert res_a.json()["company_id"] == company_a.id
    assert res_a.json()["brand_voice"] == "Alpha Voice"

    # Admin B reads profile -> receives Beta, NOT Alpha
    res_b = client.get("/api/v1/company/ai-profile", headers=auth_headers(admin_b))
    assert res_b.status_code == 200
    assert res_b.json()["company_id"] == company_b.id
    assert res_b.json()["brand_voice"] == "Beta Voice"

    # Admin A modifies profile -> Beta remains completely unaffected
    client.put(
        "/api/v1/company/ai-profile",
        headers=auth_headers(admin_a),
        json={"brand_voice": "Alpha Brand V2"},
    )

    res_b_after = client.get("/api/v1/company/ai-profile", headers=auth_headers(admin_b))
    assert res_b_after.json()["brand_voice"] == "Beta Voice"
    assert res_b_after.json()["company_id"] == company_b.id


def test_unauthenticated_requests_rejected(client: TestClient):
    """
    Requests lacking a valid Bearer token must return 401 Unauthorized.
    """
    # GET without token
    res_get = client.get("/api/v1/company/ai-profile")
    assert res_get.status_code == 401

    # PUT without token
    res_put = client.put(
        "/api/v1/company/ai-profile",
        json={"brand_voice": "Unauthorized Voice"},
    )
    assert res_put.status_code == 401

    # Invalid token format
    res_invalid = client.get(
        "/api/v1/company/ai-profile",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert res_invalid.status_code == 401


def test_response_does_not_expose_internal_fields(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    Verify response serialization conforms strictly to CompanyAIProfileResponse.
    Does not expose sensitive database internals.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    headers = auth_headers(admin)

    res = client.put(
        "/api/v1/company/ai-profile",
        headers=headers,
        json={"brand_voice": "Clean Voice"},
    )
    data = res.json()
    expected_keys = {
        "id",
        "company_id",
        "products_services",
        "target_audience",
        "preferred_writing_style",
        "brand_voice",
        "marketing_goals",
        "company_guidelines",
        "upcoming_projects",
        "partner_companies",
        "achievements",
        "created_at",
        "updated_at",
    }
    assert set(data.keys()) == expected_keys


def test_put_ai_profile_invalid_payload_rejected(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    Verify schema validation rejects invalid field types with 422 Unprocessable Entity.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    headers = auth_headers(admin)

    # Invalid type for string field (e.g. dict where str expected)
    res = client.put(
        "/api/v1/company/ai-profile",
        headers=headers,
        json={"products_services": {"nested": "not_a_string"}},
    )
    assert res.status_code == 422
    assert "detail" in res.json()


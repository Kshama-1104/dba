from fastapi.testclient import TestClient

from backend.app.models.user import UserRole
from backend.app.services.blog_format_service import create_or_update_blog_format


def test_get_blog_format_not_found(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    GET /api/v1/company/blog-format returns 404 when no format has been configured.
    Accessible to Company Admin, Editor, and Reviewer.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    headers = auth_headers(admin)

    response = client.get("/api/v1/company/blog-format", headers=headers)
    assert response.status_code == 404
    assert "no active global blog format" in response.json()["detail"].lower()


def test_company_admin_cannot_modify_or_activate_blog_format(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session,
):
    """
    Frozen Product Requirements (Doc 1 Permission Matrix):
    Company Admin has VIEW ONLY access to Global Blog Format.
    Company Admin attempting to PUT or ACTIVATE format must be rejected with 403 Forbidden.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    headers = auth_headers(admin)

    # Initial format exists
    create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in={"title_structure": "Initial Format"},
    )

    # Admin CAN read active format
    res_get = client.get("/api/v1/company/blog-format", headers=headers)
    assert res_get.status_code == 200

    # Admin CAN list versions
    res_list = client.get("/api/v1/company/blog-format/versions", headers=headers)
    assert res_list.status_code == 200

    # Admin CANNOT create or update format (403 Forbidden)
    res_put = client.put(
        "/api/v1/company/blog-format",
        headers=headers,
        json={"title_structure": "Admin Attempted Update"},
    )
    assert res_put.status_code == 403

    # Admin CANNOT activate historical format (403 Forbidden)
    res_act = client.post(
        "/api/v1/company/blog-format/versions/1/activate",
        headers=headers,
    )
    assert res_act.status_code == 403


def test_put_blog_format_by_editor_creates_version_1(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    Editor has authority to create Global Blog Format.
    PUT /api/v1/company/blog-format creates Version 1 and activates it.
    """
    company = create_company()
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)
    headers = auth_headers(editor)

    payload = {
        "title_structure": "Primary keyword in H1, maximum 60 characters",
        "introduction_structure": "Hook, industry context, thesis",
        "heading_structure": "H2 main sections with H3 subsections",
        "main_content_structure": "Data-driven insights, bullet points, code snippets",
        "conclusion_structure": "Summary, action checklist, CTA",
        "call_to_action": "Request a platform demo",
        "preferred_writing_style": "Authoritative and engaging",
    }

    response = client.put("/api/v1/company/blog-format", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["company_id"] == company.id
    assert data["version"] == 1
    assert data["is_active"] is True
    assert data["format_definition"]["title_structure"] == "Primary keyword in H1, maximum 60 characters"
    assert data["format_definition"]["call_to_action"] == "Request a platform demo"


def test_put_blog_format_by_editor_creates_version_2(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session,
):
    """
    Editor updates Global Blog Format.
    Creating an update creates Version 2 and deactivates Version 1.
    """
    company = create_company()
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)
    headers = auth_headers(editor)

    # Initial format V1 exists
    create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in={"title_structure": "Initial Title Rule"},
    )

    update_payload = {
        "title_structure": "Updated H1 Rule by Editor",
        "call_to_action": "Download free e-book",
    }
    response = client.put("/api/v1/company/blog-format", headers=headers, json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == 2
    assert data["is_active"] is True
    assert data["format_definition"]["title_structure"] == "Updated H1 Rule by Editor"


def test_get_format_versions_list(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session,
):
    """
    GET /api/v1/company/blog-format/versions returns the complete version history.
    Accessible to Admin, Editor, Reviewer.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    headers = auth_headers(admin)

    # Create V1 and V2
    create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in={"title_structure": "V1 Title"},
    )
    create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in={"title_structure": "V2 Title"},
    )

    response = client.get("/api/v1/company/blog-format/versions", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_versions"] == 2
    assert data["active_version"] == 2
    assert len(data["formats"]) == 2
    assert data["formats"][0]["version"] == 2
    assert data["formats"][1]["version"] == 1


def test_editor_can_activate_historical_version(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session,
):
    """
    Editor can GET a specific historical version, then POST to activate it.
    Active format changes from V2 to V1.
    """
    company = create_company()
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)
    headers = auth_headers(editor)

    create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in={"title_structure": "Version 1 Structure"},
    )
    create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in={"title_structure": "Version 2 Structure"},
    )

    # Retrieve Version 1 specifically
    v1_res = client.get("/api/v1/company/blog-format/versions/1", headers=headers)
    assert v1_res.status_code == 200
    assert v1_res.json()["version"] == 1
    assert v1_res.json()["is_active"] is False

    # Editor activates Version 1
    act_res = client.post("/api/v1/company/blog-format/versions/1/activate", headers=headers)
    assert act_res.status_code == 200
    assert act_res.json()["version"] == 1
    assert act_res.json()["is_active"] is True

    # Active endpoint now returns V1
    active_res = client.get("/api/v1/company/blog-format", headers=headers)
    assert active_res.status_code == 200
    assert active_res.json()["version"] == 1


def test_reviewer_read_only_access(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session,
):
    """
    Document 1 Permission Model:
    Reviewers have Read-Only access to global blog templates.
    Reviewers attempting to modify or activate formats must be rejected with 403 Forbidden.
    """
    company = create_company()
    reviewer = create_user(company_id=company.id, role=UserRole.REVIEWER)
    headers = auth_headers(reviewer)

    create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in={"title_structure": "Existing Format"},
    )

    # Reviewer CAN read active format
    res_get = client.get("/api/v1/company/blog-format", headers=headers)
    assert res_get.status_code == 200

    # Reviewer CAN list versions
    res_list = client.get("/api/v1/company/blog-format/versions", headers=headers)
    assert res_list.status_code == 200

    # Reviewer CANNOT modify format (403)
    res_put = client.put(
        "/api/v1/company/blog-format",
        headers=headers,
        json={"title_structure": "Unauthorized Format Update"},
    )
    assert res_put.status_code == 403

    # Reviewer CANNOT activate format (403)
    res_act = client.post(
        "/api/v1/company/blog-format/versions/1/activate",
        headers=headers,
    )
    assert res_act.status_code == 403


def test_tenant_isolation_enforced(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session,
):
    """
    Company A user cannot read, update, or activate Company B's Global Blog Format.
    """
    company_a = create_company(name="Alpha Corp")
    company_b = create_company(name="Beta Corp")

    admin_a = create_user(company_id=company_a.id, role=UserRole.COMPANY_ADMIN)
    admin_b = create_user(company_id=company_b.id, role=UserRole.COMPANY_ADMIN)

    create_or_update_blog_format(
        db=db_session,
        company_id=company_a.id,
        format_in={"title_structure": "Alpha Format Rules"},
    )
    create_or_update_blog_format(
        db=db_session,
        company_id=company_b.id,
        format_in={"title_structure": "Beta Format Rules"},
    )

    # Admin A reads format -> receives Alpha format
    res_a = client.get("/api/v1/company/blog-format", headers=auth_headers(admin_a))
    assert res_a.status_code == 200
    assert res_a.json()["company_id"] == company_a.id
    assert res_a.json()["format_definition"]["title_structure"] == "Alpha Format Rules"

    # Admin B reads format -> receives Beta format
    res_b = client.get("/api/v1/company/blog-format", headers=auth_headers(admin_b))
    assert res_b.status_code == 200
    assert res_b.json()["company_id"] == company_b.id
    assert res_b.json()["format_definition"]["title_structure"] == "Beta Format Rules"


def test_unauthenticated_requests_rejected(client: TestClient):
    """
    Unauthenticated requests return 401 Unauthorized.
    """
    res_get = client.get("/api/v1/company/blog-format")
    assert res_get.status_code == 401

    res_put = client.put("/api/v1/company/blog-format", json={"title_structure": "Test"})
    assert res_put.status_code == 401

    res_list = client.get("/api/v1/company/blog-format/versions")
    assert res_list.status_code == 401


def test_mandatory_baseline_sections_omission_rejected(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    Payload attempting to strip mandatory baseline sections (e.g. omitting Conclusion)
    must be rejected with 422 Unprocessable Entity.
    Tested with Editor user (authorized to modify).
    """
    company = create_company()
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)
    headers = auth_headers(editor)

    invalid_payload = {
        "required_sections": ["Title", "Introduction", "Headings", "Main Content"]
        # Missing "Conclusion"
    }

    response = client.put(
        "/api/v1/company/blog-format",
        headers=headers,
        json=invalid_payload,
    )
    assert response.status_code == 422
    assert "Conclusion" in str(response.json())

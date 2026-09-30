from fastapi.testclient import TestClient

from backend.app.models.company_settings import CompanySettings
from backend.app.models.user import UserRole


def test_phase1_health_endpoints(client: TestClient):
    """
    Verify fundamental service and database health checks pass.
    """
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    res_db = client.get("/health/database")
    assert res_db.status_code == 200
    assert res_db.json()["status"] == "healthy"
    assert res_db.json()["test_result"] == 1


def test_phase1_auth_login_and_me(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    Verify login flow, credential verification, and me profile inspection.
    """
    company = create_company()
    user = create_user(
        company_id=company.id,
        role=UserRole.COMPANY_ADMIN,
        password="MySecretPassword123!",
    )

    # Failed login with wrong password
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401

    # Successful login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "MySecretPassword123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token is not None

    # GET /api/v1/me with token
    me_res = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["user_id"] == user.id
    assert me_res.json()["role"] == UserRole.COMPANY_ADMIN.value


def test_phase1_role_guard_admin_test(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    Verify require_role strictly gates endpoints against non-admin roles.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    reviewer = create_user(company_id=company.id, role=UserRole.REVIEWER)
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)

    # Admin access granted
    res_admin = client.get("/api/v1/admin/test", headers=auth_headers(admin))
    assert res_admin.status_code == 200
    assert res_admin.json()["role"] == "company_admin"

    # Reviewer access denied (403)
    res_rev = client.get("/api/v1/admin/test", headers=auth_headers(reviewer))
    assert res_rev.status_code == 403

    # Editor access denied (403)
    res_ed = client.get("/api/v1/admin/test", headers=auth_headers(editor))
    assert res_ed.status_code == 403


def test_phase1_company_dashboard_and_settings(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session,
):
    """
    Verify Company Dashboard and Company Settings endpoints.
    """
    company = create_company(name="Acme Enterprise")
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)

    # Seed company settings
    settings = CompanySettings(
        company_id=company.id,
        notification_email="admin@acme.com",
        blog_generation_enabled=True,
        publishing_enabled=True,
    )
    db_session.add(settings)
    db_session.commit()

    # GET /api/v1/company/dashboard
    dash_res = client.get(
        "/api/v1/company/dashboard",
        headers=auth_headers(admin),
    )
    assert dash_res.status_code == 200
    assert dash_res.json()["company"]["id"] == company.id

    # GET /api/v1/company/settings
    sett_res = client.get(
        "/api/v1/company/settings",
        headers=auth_headers(admin),
    )
    assert sett_res.status_code == 200
    assert sett_res.json()["company_id"] == company.id
    assert sett_res.json()["notification_email"] == "admin@acme.com"


def test_phase1_reviewers_and_editors_listing(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    """
    Verify company user directories for Reviewers and Editors.
    """
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    create_user(company_id=company.id, role=UserRole.REVIEWER)
    create_user(company_id=company.id, role=UserRole.EDITOR)

    res_revs = client.get(
        "/api/v1/company/reviewers",
        headers=auth_headers(admin),
    )
    assert res_revs.status_code == 200
    assert res_revs.json()["count"] >= 1

    res_eds = client.get(
        "/api/v1/company/editors",
        headers=auth_headers(admin),
    )
    assert res_eds.status_code == 200
    assert res_eds.json()["count"] >= 1


def test_phase1_registration_captcha_generation(client: TestClient):
    """
    Verify company registration multi-step session: Step 1 -> OTP -> CAPTCHA generation.
    """
    import uuid
    uid = uuid.uuid4().hex[:6]
    start_res = client.post(
        "/api/v1/registration/company",
        json={
            "company_name": f"Registration Test Co {uid}",
            "company_description": "Valid test company",
            "logo_url": "https://example.com/logo.png",
            "company_type": "Private",
            "industry": "Software",
            "country_region": "United States",
            "company_email": f"reg_{uid}@example.com",
        },
    )
    assert start_res.status_code == 201
    token = start_res.json()["registration_token"]
    assert token is not None

    # Step 1 -> Send OTP
    send_otp_res = client.post(
        f"/api/v1/registration/otp/send?registration_token={token}"
    )
    assert send_otp_res.status_code == 200
    otp = send_otp_res.json()["development_otp"]

    # Verify OTP -> Advances to CAPTCHA step
    verify_otp_res = client.post(
        "/api/v1/registration/otp/verify",
        json={"registration_token": token, "otp": otp},
    )
    assert verify_otp_res.status_code == 200

    # Step 2 -> Generate CAPTCHA
    captcha_res = client.post(
        f"/api/v1/registration/captcha/generate?registration_token={token}"
    )
    assert captcha_res.status_code == 200
    data = captcha_res.json()
    assert "development_captcha" in data or "message" in data
